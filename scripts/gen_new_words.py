"""Offline generation of the catalogue entry for a word we don't have yet.

Measuring the catalogue against the New General Service List found 160 of the
thousand most common English words missing outright — `would` (rank 36),
`company` (107), `something` (138) — while rarer words were being taught. Those
gaps need a Russian translation and a CEFR level before `gen_examples.py` can
give them sentences, and before the picker can place them at all.

The level comes from the same prompt the background tagger uses, so words added
here land on the same scale as the rest of the catalogue rather than quietly
forming a second, differently-calibrated half.

Every candidate is checked mechanically before it is kept: a translation that
leaks the English answer, is not actually Russian, or is a paragraph rather
than a gloss is rejected and regenerated with the reason fed back. Nothing
reaches the migration unverified.

`polysemous` marks words like `charge`, `stock` and `firm`, whose senses are
unrelated enough that a one-translation card teaches one sense as if it were
the whole word. They are kept — they are genuinely frequent — but the flag lets
the queue hold them back behind the unambiguous words of the same band.

Usage:
    python scripts/gen_new_words.py --in words.json --out entries.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.levels import LEVELS  # noqa: E402
from app.services.level_tagger import SYSTEM_PROMPT as LEVEL_SCALE  # noqa: E402
from scripts.gen_examples import (  # noqa: E402
    DEFAULT_MODEL,
    call,
    read_api_key,
)

MAX_TRANSLATION_LEN = 60

SYSTEM = f"""Ты составляешь словарную статью для карточки изучения английского.

Для каждого английского слова верни:

1. translation — перевод на русский. Коротко, как в словаре: одно слово или
   два-три через « / ». НЕ предложение, НЕ объяснение. Без латиницы вообще —
   перевод показывается как вариант ответа в тесте, и любая английская буква
   в нём выдаёт ответ.

2. level — уровень CEFR по шкале ниже.

3. polysemous — true, если у слова несколько НЕ связанных между собой значений,
   каждое из которых частотно (charge: «заряд» и «плата» и «обвинение»;
   stock: «запас» и «акции»). Если значения близки или одно явно главное —
   false. Это не про оттенки, а про то, что одним переводом слово не описать.

{LEVEL_SCALE}

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "translation": {"type": "STRING"},
            "level": {"type": "STRING", "enum": list(LEVELS)},
            "polysemous": {"type": "BOOLEAN"},
        },
        "required": ["id", "translation", "level", "polysemous"],
    },
}

_LATIN = re.compile(r"[A-Za-z]")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def check(row: dict[str, Any], word: dict[str, Any]) -> list[str]:
    """Every reason this entry is unusable. Empty list means it's good."""
    problems: list[str] = []
    translation = (row.get("translation") or "").strip()
    level = (row.get("level") or "").strip().upper()

    if not translation:
        problems.append("пустой перевод")
        return problems
    # The gloss is shown as a quiz option before the answer is revealed, so any
    # Latin in it hands over the English word being asked for.
    if _LATIN.search(translation):
        problems.append(f"в переводе есть латиница: «{translation}»")
    if not _CYRILLIC.search(translation):
        problems.append(f"перевод не по-русски: «{translation}»")
    if len(translation) > MAX_TRANSLATION_LEN:
        problems.append(
            f"перевод длиной {len(translation)} символов — нужна короткая глосса, не объяснение"
        )
    # A gloss is a word or a few; a sentence means the model explained instead
    # of translating, and it will not fit on a button.
    if translation.count(" ") > 6 or translation.endswith("."):
        problems.append(f"перевод похож на предложение, а не на словарную глоссу: «{translation}»")
    if level not in LEVELS:
        problems.append(f"неизвестный уровень «{row.get('level')}»")
    return problems


def ask(
    model: str, key: str, words: list[dict[str, Any]], notes: dict[int, list[str]] | None = None
) -> dict[int, dict[str, Any]]:
    lines = []
    for w in words:
        line = f"{w['id']}. {w['w']}"
        for problem in (notes or {}).get(w["id"], []):
            line += f"\n    ИСПРАВЬ: {problem}"
        lines.append(line)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            # A dictionary gloss has a right answer — variety is not a virtue
            # here, unlike the example sentences.
            "temperature": 0,
        },
    }
    rows = call(model, key, payload)
    return {int(r["id"]): r for r in rows if isinstance(r, dict) and "id" in r}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = read_api_key()
    words = json.loads(Path(args.src).read_text(encoding="utf-8"))

    out_path = Path(args.dst)
    done: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        done = {str(r["id"]): r for r in json.loads(out_path.read_text(encoding="utf-8"))}
        print(f"resuming — {len(done)} already generated")

    by_id = {w["id"]: w for w in words}
    todo = [w for w in words if str(w["id"]) not in done]
    rejected_total = 0

    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        notes: dict[int, list[str]] = {}
        pending = {w["id"]: w for w in chunk}

        for _round in range(args.rounds):
            if not pending:
                break
            rows = ask(args.model, key, list(pending.values()), notes)
            notes = {}
            still: dict[int, dict[str, Any]] = {}
            for wid, word in pending.items():
                row = rows.get(wid)
                if row is None:
                    still[wid] = word
                    continue
                problems = check(row, word)
                if problems:
                    rejected_total += 1
                    notes[wid] = problems
                    still[wid] = word
                    continue
                done[str(wid)] = {
                    "id": wid,
                    "w": word["w"],
                    "rank": word.get("rank"),
                    "translation": row["translation"].strip(),
                    "level": row["level"].strip().upper(),
                    "polysemous": bool(row.get("polysemous")),
                }
            pending = still

        if pending:
            print(f"  не смог сгенерировать: {[by_id[i]['w'] for i in pending]}")

        out_path.write_text(
            json.dumps(sorted(done.values(), key=lambda r: r["id"]), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(
            f"  {min(start + args.batch, len(todo))}/{len(todo)} — "
            f"принято {len(done)}, отсеяно {rejected_total}"
        )

    print(f"done: {len(done)} / {len(words)} -> {out_path}")
    print(f"отсеяно автопроверками: {rejected_total}")


if __name__ == "__main__":
    main()
