"""Offline assignment of catalogue words to the thematic collections.

The packs were hand-made and it showed: 22 themes of exactly 20 words, with
`Погода и природа` fused into one and `Город и транспорт` duplicating the
travel pack, while `распорядок дня`, `числительные`, `покупки` and `внешность`
— all of them first-lesson material in every published syllabus — were missing
outright. 533 catalogue words belonged to no pack at all, among them `why`,
`please`, `around`, `every` and `also`.

This classifies every word the bot can teach against the taxonomy in
`app.domain.themes`, which follows the Cambridge A2 Key and British Council
topic lists rather than our own invention.

A word gets one theme or none. "None" is a normal answer — `become`,
`important` and `situation` are carried by the corpus-rank stream instead, and
forcing them into a theme would only dilute it.

Usage:
    python scripts/classify_themes.py --in words.json --out themes.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.themes import NO_THEME, THEMES  # noqa: E402
from scripts.gen_examples import DEFAULT_MODEL, call, read_api_key  # noqa: E402

_CATALOGUE = "\n".join(f"  {t.slug} — {t.title.split(' ', 1)[-1]}: {t.hint}" for t in THEMES)

SYSTEM = f"""Ты раскладываешь английские слова по темам для словарного тренажёра.

Темы:
{_CATALOGUE}
  {NO_THEME} — слово не про конкретную тему

Правила:

1. Одно слово — ОДНА тема. Выбирай ту, в которой слово встретится чаще всего
   в жизни обычного человека, а не ту, где оно теоретически возможно.

2. Ставь "{NO_THEME}" смело. Общие и абстрактные слова (become, important,
   situation, result, provide) темы не имеют, и это нормально — их даёт
   частотный поток. Лучше "{NO_THEME}", чем натянутая тема: тема из натянутых
   слов бесполезна для того, кто её выбрал.

3. Смотри на РУССКИЙ перевод — он задаёт значение, которое учит карточка.
   Если у английского слова много значений, тему определяет перевод.

4. Слово общего действия (go, make, take, want) — почти всегда "{NO_THEME}",
   даже если его можно употребить в теме.

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

SLUGS = [t.slug for t in THEMES] + [NO_THEME]

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "theme": {"type": "STRING", "enum": SLUGS},
        },
        "required": ["id", "theme"],
    },
}


def ask(model: str, key: str, words: list[dict[str, Any]]) -> dict[int, str]:
    lines = [f"{w['id']}. {w['w']} — {w['t']}" for w in words]
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0,
        },
    }
    rows = call(model, key, payload)
    out = {}
    for r in rows:
        if isinstance(r, dict) and "id" in r and r.get("theme") in SLUGS:
            out[int(r["id"])] = r["theme"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--batch", type=int, default=60)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = read_api_key()
    words = json.loads(Path(args.src).read_text(encoding="utf-8"))

    out_path = Path(args.dst)
    done: dict[str, str] = {}
    if out_path.exists():
        done = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"resuming — {len(done)} already classified")

    todo = [w for w in words if str(w["id"]) not in done]
    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        try:
            got = ask(args.model, key, chunk)
        except RuntimeError as exc:
            print(f"  партия пропущена: {exc}")
            continue
        for w in chunk:
            if w["id"] in got:
                done[str(w["id"])] = got[w["id"]]
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {min(start + args.batch, len(todo))}/{len(todo)} — разложено {len(done)}")

    print(f"done: {len(done)} / {len(words)} -> {out_path}")


if __name__ == "__main__":
    main()
