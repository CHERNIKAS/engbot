"""Offline generation of the two example sentences a word card can carry.

`example_sentence` is the one the cloze card blanks out — it is useless unless
the target word appears in it in a maskable form, and mastery now *requires*
typed answers, so a word without one cannot be learned at all.

`abstract_example_en/ru` is the hint shown on a push card: it describes the
situation around the word without naming it, so it gives context without
handing over the answer.

Every candidate is checked mechanically before it is kept — the same masking
regex the bot uses, a spoiler check, a length check, and a readability check
against our own levelled catalogue. Anything that fails is regenerated with the
failure fed back to the model. Nothing reaches the migration unverified.

Usage:
    python scripts/gen_examples.py --in words.json --out examples.json [--batch 20]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.levels import LEVELS, index  # noqa: E402

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Must stay identical to push_service._CLOZE_INFLECT — a sentence that this
# accepts but the bot's masker rejects is exactly the silent failure this
# script exists to prevent.
_CLOZE_INFLECT = r"(?:s|es|ed|d|ing|ly|er|est)?"

MIN_WORDS = 4
MAX_WORDS = 14
# Words that must survive after the target is blanked out. A phrasebook entry
# whose "example" is the phrase itself masks down to "___." — a cloze card with
# nothing left to infer from.
MIN_CONTEXT_WORDS = 3

SYSTEM = """Ты составляешь примеры для карточек изучения английских слов.

Для каждого слова верни ДВА предложения.

1. sentence — обычное английское предложение, где слово ОБЯЗАТЕЛЬНО стоит
   дословно (можно с окончанием -s/-es/-ed/-ing/-ly/-er/-est, но НЕ
   неправильной формой: для "go" подойдёт "goes", но НЕ "went").
   От 4 до 14 слов. Простая бытовая ситуация. Остальные слова в предложении
   должны быть НЕ СЛОЖНЕЕ самого слова — если слово уровня A1, всё предложение
   должно быть на A1.

2. hint_en — другое предложение, которое описывает ту же ситуацию, но САМОГО
   СЛОВА В НЁМ БЫТЬ НЕ ДОЛЖНО (ни в какой форме). Это подсказка: человек
   должен понять смысл и вспомнить слово сам. Используй синоним или описание.

3. hint_ru — перевод hint_en на русский, естественный, не подстрочник.

ВАЖНО: hint_en тоже должен быть НЕ СЛОЖНЕЕ уровня слова. Подсказка к слову A1
не может содержать слова уровня B2 — человек читает её именно тогда, когда
застрял, и непонятная подсказка хуже, чем никакой.

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "sentence": {"type": "STRING"},
            "hint_en": {"type": "STRING"},
            "hint_ru": {"type": "STRING"},
        },
        "required": ["id", "sentence", "hint_en", "hint_ru"],
    },
}


def contains_word(sentence: str, word: str) -> bool:
    """Exactly the test the bot's cloze masker applies."""
    if not sentence or not word:
        return False
    pattern = re.compile(rf"\b{re.escape(word)}{_CLOZE_INFLECT}\b", re.IGNORECASE)
    return pattern.search(sentence) is not None


_TOKEN = re.compile(r"[A-Za-z']+")


def too_hard_words(sentence: str, level: str | None, lexicon: dict[str, str]) -> list[str]:
    """Words in the sentence that our own catalogue rates ABOVE the target level.

    Uses the levelled catalogue as the yardstick rather than a guess: an A1 word
    explained with B2 vocabulary teaches nothing. Words we haven't levelled are
    ignored — absence of data isn't evidence of difficulty.
    """
    if not level:
        return []
    ceiling = index(level)
    out = []
    for token in _TOKEN.findall(sentence.lower()):
        got = lexicon.get(token)
        if got and index(got) > ceiling:
            out.append(token)
    return sorted(set(out))


def check(
    row: dict[str, Any],
    word: dict[str, Any],
    lexicon: dict[str, str],
    hints_only: bool = False,
) -> list[str]:
    """Every reason this candidate is unusable. Empty list means it's good.

    `hints_only` is for words that already have a hand-written example and need
    only the context hint: judging the throwaway sentence would reject good
    hints for a field that is never written.
    """
    problems: list[str] = []
    sentence = (row.get("sentence") or "").strip()
    hint_en = (row.get("hint_en") or "").strip()
    hint_ru = (row.get("hint_ru") or "").strip()
    target = word["w"]

    if hints_only:
        if hint_en and contains_word(hint_en, target):
            problems.append(f"в hint_en есть само слово '{target}' — это спойлер")
        if not hint_en or not hint_ru:
            problems.append("пустая подсказка")
        hard = too_hard_words(hint_en, word.get("lvl"), lexicon)
        if hard:
            problems.append(
                f"в hint_en слова сложнее уровня {word.get('lvl')}: {', '.join(hard[:4])}"
            )
        return problems

    if not contains_word(sentence, target):
        problems.append(f"в sentence нет слова '{target}' в маскируемой форме")
    n = len(sentence.split())
    if not (MIN_WORDS <= n <= MAX_WORDS):
        problems.append(f"длина sentence {n} слов, нужно {MIN_WORDS}-{MAX_WORDS}")
    else:
        masked = re.sub(
            rf"{re.escape(target)}{_CLOZE_INFLECT}", "___", sentence, flags=re.IGNORECASE
        )
        left = len(_TOKEN.findall(masked))
        if left < MIN_CONTEXT_WORDS:
            problems.append(
                f"после скрытия слова остаётся {left} слов — восстановить не по чему"
            )
    if hint_en and contains_word(hint_en, target):
        problems.append(f"в hint_en есть само слово '{target}' — это спойлер")
    if not hint_en or not hint_ru:
        problems.append("пустая подсказка")
    # Readability applies to the hint too. The first run wrote "concerning" as
    # the hint for the A1 word "about" and "following" for "after" — a hint the
    # learner can't read is worse than none, because it appears on the card
    # exactly when they're stuck.
    for field, text in (("sentence", sentence), ("hint_en", hint_en)):
        hard = too_hard_words(text, word.get("lvl"), lexicon)
        if hard:
            problems.append(
                f"в {field} слова сложнее уровня {word.get('lvl')}: {', '.join(hard[:4])}"
            )
    return problems


def read_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("GEMINI_API_KEY not found (env or .env)")


def call(model: str, key: str, payload: dict[str, Any], attempts: int = 4) -> list[dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for attempt in range(attempts):
        req = urllib.request.Request(
            API.format(model=model, key=key),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 503):
                raise
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last = type(exc).__name__
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"batch failed after {attempts} attempts: {last}")


def ask(
    model: str, key: str, words: list[dict[str, Any]], notes: dict[int, list[str]] | None = None
) -> dict[int, dict[str, Any]]:
    lines = []
    for w in words:
        line = f"{w['id']}. {w['w']} ({w.get('lvl') or 'A2'}) — {w['t']}"
        for problem in (notes or {}).get(w["id"], []):
            line += f"\n    ИСПРАВЬ: {problem}"
        lines.append(line)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.7,  # examples should vary; 0 makes them all alike
        },
    }
    rows = call(model, key, payload)
    return {int(r["id"]): r for r in rows if isinstance(r, dict) and "id" in r}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--lexicon", dest="lex", required=True, help="JSON {word: level}")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=3, help="retry rounds for rejected rows")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--hints-only",
        action="store_true",
        help="word already has an example; judge only the context hint",
    )
    args = ap.parse_args()

    key = read_api_key()
    words = json.loads(Path(args.src).read_text(encoding="utf-8"))
    lexicon = {k.lower(): v for k, v in json.loads(Path(args.lex).read_text(encoding="utf-8")).items()}

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
                problems = check(row, word, lexicon, hints_only=args.hints_only)
                if problems:
                    rejected_total += 1
                    notes[wid] = problems
                    still[wid] = word
                    continue
                done[str(wid)] = {
                    "id": wid,
                    "sentence": (row.get("sentence") or "").strip(),
                    "hint_en": row["hint_en"].strip(),
                    "hint_ru": row["hint_ru"].strip(),
                }
            pending = still

        if pending:
            print(f"  не смог сгенерировать: {[by_id[i]['w'] for i in pending]}")

        out_path.write_text(
            json.dumps(sorted(done.values(), key=lambda r: r["id"]), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"  {min(start + args.batch, len(todo))}/{len(todo)} — принято {len(done)}, отсеяно {rejected_total}")

    print(f"done: {len(done)} / {len(words)} words -> {out_path}")
    print(f"отсеяно автопроверками: {rejected_total}")


if __name__ == "__main__":
    main()
