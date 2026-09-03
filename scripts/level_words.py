"""Offline CEFR + frequency tagging for words that have no `level` yet.

One-shot content job, not a runtime path: reads a JSON dump of unleveled words,
asks Gemini to tag them in batches, and writes a resumable JSON result that gets
baked into an Alembic migration (the first run produced 0037_word_levels_freq).

Resumable by design — the free tier throws sporadic 503s and the run takes a few
minutes, so every batch is flushed to disk and an interrupted run picks up where
it stopped.

Usage:
    python scripts/level_words.py --in dump.json --out levels.json [--batch 40]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_MODEL = "gemini-3.1-flash-lite"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

SYSTEM = """Ты лексикограф. Для каждого английского слова определи:

1. level — уровень CEFR (A1, A2, B1, B2, C1, C2), на котором это слово обычно
   вводят изучающим английский как иностранный.
   A1 — базовые бытовые слова (cat, go, big).
   A2 — расширенный быт (weather, decide, careful).
   B1 — обиходно-абстрактное (achieve, opinion, reliable).
   B2 — более книжное и точное (reluctant, thorough, allocate).
   C1/C2 — редкое, узкоспециальное, книжное (ubiquitous, unwieldy).

2. freq — насколько часто слово встречается в обычном английском:
   1 = очень частое (входит в первую тысячу),
   2 = частое, 3 = среднее, 4 = редкое, 5 = очень редкое / узкий термин.

Термин из узкой области (крипта, медицина, юриспруденция) получает уровень по
своей лексической сложности, а freq — 4 или 5.

КАЛИБРОВКА. Ниже — эталонная шкала этого курса. Ориентируйся на неё, а не на
собственное представление о сложности: шкала курса заметно мягче типичных
учебных списков.

A1: loud, worry, place, work, try, market, neighbour, word, ready, enter
A2: daily, wipe, piece, mix, safe, rescue, whisper, breathe, list, fix
B1: certain, aware, perfect, settle, relate, alone, purpose, honest, legal, replace
B2: stability, variable, condemn, subsequent, abstract, phase, ambition, ambiguous, adequate, constraint

Замечено, что модели завышают уровень примерно на один шаг. Если колеблешься
между двумя соседними уровнями — выбирай МЛАДШИЙ.

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "level": {"type": "STRING", "enum": LEVELS},
            "freq": {"type": "INTEGER"},
        },
        "required": ["id", "level", "freq"],
    },
}


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
    """POST one batch, retrying the free tier's sporadic 503 / rate limiting."""
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for attempt in range(attempts):
        req = urllib.request.Request(
            API.format(model=model, key=key),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = read_api_key()
    words = json.loads(Path(args.src).read_text(encoding="utf-8"))

    out_path = Path(args.dst)
    done: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        done = {str(r["id"]): r for r in json.loads(out_path.read_text(encoding="utf-8"))}
        print(f"resuming — {len(done)} already tagged")

    todo = [w for w in words if str(w["id"]) not in done]
    print(f"{len(todo)} to tag in batches of {args.batch}")

    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        listing = "\n".join(
            f"{w['id']}. {w['w']} — {w['t'] or '(нет перевода)'}" for w in chunk
        )
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": listing}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
                "temperature": 0,
            },
        }
        rows = call(args.model, key, payload)
        for r in rows:
            if r.get("level") in LEVELS:
                done[str(r["id"])] = {
                    "id": int(r["id"]),
                    "level": r["level"],
                    "freq": max(1, min(5, int(r.get("freq", 3)))),
                }
        out_path.write_text(
            json.dumps(sorted(done.values(), key=lambda r: r["id"]), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"  {min(start + args.batch, len(todo))}/{len(todo)} — total tagged {len(done)}")

    print(f"done: {len(done)} words -> {out_path}")


if __name__ == "__main__":
    main()
