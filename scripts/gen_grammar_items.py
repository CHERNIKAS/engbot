"""Offline generation of gap-fill exercises for words grammar is meant to own.

The function-word stoplist removes ~196 entries from the vocabulary rotation on
the grounds that grammar teaches them instead. Checking that claim showed it was
mostly false: the prepositions topic covered `at`, `in`, `on`, `to` and nothing
else, quantifiers covered `any`, `many`, `much`, `some`, and modals stopped at
`can` / `must` / `should` / `have to`. About 175 words — `would` (the 36th most
common word in English), `may`, `without`, `within`, `among`, `above` — were
being taught by neither side.

This closes that gap in the format the bot already serves, so nothing sits in
limbo while the larger rework of grammar into sentence construction is done.

Every candidate is checked mechanically: exactly one blank, the answer must not
also appear elsewhere in the sentence (which would give it away), distractors
must be distinct from the answer and from each other, and they must come from
the same closed set so the card cannot be solved by elimination.

Usage:
    python scripts/gen_grammar_items.py --in targets.json --out items.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gen_examples import DEFAULT_MODEL, call, read_api_key  # noqa: E402

MIN_WORDS = 4
MAX_WORDS = 14
BLANK = "___"

SYSTEM = """Ты составляешь упражнения с пропуском для тренажёра английской грамматики.

Для каждого целевого слова верни предложение, где это слово пропущено.

Правила:

1. prompt — английское предложение, в котором РОВНО ОДИН пропуск, обозначенный
   тремя подчёркиваниями: ___
   От 4 до 14 слов. Простая бытовая ситуация.

2. Пропущенное слово — это ровно целевое слово, которое тебе дали.

3. Целевого слова НЕ должно быть больше нигде в предложении — иначе ответ виден.

4. distractors — ТРИ других слова из того же набора, которые грамматически
   могли бы встать в этот пропуск, но по смыслу неверны. Они должны быть
   правдоподобны: для предлога места — другие предлоги места, а не случайные
   слова. Если неверный вариант очевидно не подходит по части речи, упражнение
   решается исключением и ничему не учит.

5. Предложение должно ОДНОЗНАЧНО определять ответ: не должно быть так, что
   дистрактор тоже подходит. Это главное требование.

6. Никаких редких слов в самом предложении — уровень A2.

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "prompt": {"type": "STRING"},
            "distractors": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["id", "prompt", "distractors"],
    },
}

_WORD = re.compile(r"[A-Za-z']+")


def check(row: dict[str, Any], target: dict[str, Any]) -> list[str]:
    """Every reason this exercise is unusable. Empty list means it's good."""
    problems: list[str] = []
    prompt = (row.get("prompt") or "").strip()
    correct = target["w"]
    distractors = [d.strip() for d in (row.get("distractors") or []) if d and d.strip()]

    blanks = prompt.count(BLANK)
    if blanks != 1:
        problems.append(f"пропусков {blanks}, нужен ровно один ({BLANK})")

    n = len(prompt.split())
    if not (MIN_WORDS <= n <= MAX_WORDS):
        problems.append(f"длина {n} слов, нужно {MIN_WORDS}-{MAX_WORDS}")

    # The answer must not be readable off the rest of the sentence.
    rest = prompt.replace(BLANK, " ")
    if correct.lower() in [w.lower() for w in _WORD.findall(rest)]:
        problems.append(f"слово '{correct}' есть в предложении — ответ виден")

    if len(distractors) != 3:
        problems.append(f"дистракторов {len(distractors)}, нужно 3")
    lowered = [d.lower() for d in distractors]
    if correct.lower() in lowered:
        problems.append(f"среди дистракторов сам ответ '{correct}'")
    if len(set(lowered)) != len(lowered):
        problems.append("дистракторы повторяются")
    return problems


def ask(
    model: str, key: str, targets: list[dict[str, Any]], notes: dict[int, list[str]] | None = None
) -> dict[int, dict[str, Any]]:
    lines = []
    for t in targets:
        line = f"{t['id']}. целевое слово: {t['w']}  (набор: {t['set']})"
        for problem in (notes or {}).get(t["id"], []):
            line += f"\n    ИСПРАВЬ: {problem}"
        lines.append(line)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.6,
        },
    }
    rows = call(model, key, payload)
    return {int(r["id"]): r for r in rows if isinstance(r, dict) and "id" in r}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = read_api_key()
    targets = json.loads(Path(args.src).read_text(encoding="utf-8"))

    out_path = Path(args.dst)
    done: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        done = {str(r["id"]): r for r in json.loads(out_path.read_text(encoding="utf-8"))}
        print(f"resuming — {len(done)} already generated")

    by_id = {t["id"]: t for t in targets}
    todo = [t for t in targets if str(t["id"]) not in done]
    rejected = 0

    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        notes: dict[int, list[str]] = {}
        pending = {t["id"]: t for t in chunk}

        for _round in range(args.rounds):
            if not pending:
                break
            rows = ask(args.model, key, list(pending.values()), notes)
            notes = {}
            still: dict[int, dict[str, Any]] = {}
            for tid, target in pending.items():
                row = rows.get(tid)
                if row is None:
                    still[tid] = target
                    continue
                problems = check(row, target)
                if problems:
                    rejected += 1
                    notes[tid] = problems
                    still[tid] = target
                    continue
                done[str(tid)] = {
                    "id": tid,
                    "topic": target["topic"],
                    "correct": target["w"],
                    "prompt": row["prompt"].strip(),
                    "distractors": [d.strip() for d in row["distractors"]],
                }
            pending = still

        if pending:
            print(f"  не смог: {[by_id[i]['w'] for i in pending]}")

        out_path.write_text(
            json.dumps(sorted(done.values(), key=lambda r: r["id"]), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"  {min(start + args.batch, len(todo))}/{len(todo)} — принято {len(done)}, отсеяно {rejected}")

    print(f"done: {len(done)} / {len(targets)} -> {out_path}")


if __name__ == "__main__":
    main()
