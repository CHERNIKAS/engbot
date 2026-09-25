"""Offline generation of sentence-construction exercises.

The gap-fill format the bot has cannot prove a tense is known: four options,
one blank, a 25% floor from guessing alone. A learner can pass every card in a
topic and still be unable to say the sentence. That is why the grammar module
is being rebuilt around construction — you are given the Russian and produce
the English, with nothing to pick from.

Each exercise carries the sentence twice over:

  * `en` — the answer, used by the typing mode and by the checker;
  * `slots` — the same sentence cut into choice points, used by the assisted
    mode. A slot is one decision: subject, then auxiliary, then verb form. The
    learner taps through them and each choice narrows what comes next, so the
    support is real but the grammar still has to be known — «she» must be
    followed by «doesn't», not «don't», and no amount of elimination reveals
    that.

Both modes read the same row. The assisted mode is where a topic starts; the
typing mode is what passing it requires.

Verification is mechanical and total: the slots must concatenate back into
exactly `en`, every slot must offer its own answer, and distractors must be
real alternatives from the same paradigm rather than filler.

Usage:
    python scripts/gen_constructor.py --topic tense_present_simple \\
        --spec "..." --count 100 --out phrases.json
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

MIN_WORDS = 2
# Long enough for one sentence a learner types in full. Raise it per topic
# with --max-words: the third conditional carries two clauses and an auxiliary
# stack — «If she had studied, she would have passed the exam» is ten words
# before it says anything — so a nine-word ceiling rejects the grammar itself.
MAX_WORDS = 9
MIN_OPTIONS = 2
MAX_OPTIONS = 4

SYSTEM = """Ты составляешь упражнения «построй английское предложение» для тренажёра.

Дана тема грамматики. Для каждого задания верни:

1. ru — короткое русское предложение, от 2 до 8 слов. Бытовое, простое.
   Оно должно ОДНОЗНАЧНО переводиться на английский изучаемой конструкцией.
   Избегай фраз, где возможны несколько разных времён или конструкций.

2. en — правильный английский перевод. От 2 до 9 слов.

3. alternatives — другие ДОПУСТИМЫЕ переводы этого же ru, если они есть
   (другой порядок слов, полная форма вместо сокращения: "does not" рядом с
   "doesn't"). Если вариантов нет — пустой массив.

4. slots — то же предложение en, разрезанное на точки выбора. Каждый слот это
   один кусок предложения и варианты для него:
     - correct — правильный кусок
     - options — от 2 до 4 вариантов, ОБЯЗАТЕЛЬНО включая correct

   ЖЕЛЕЗНОЕ ПРАВИЛО: если склеить все correct через пробел, должно получиться
   РОВНО en. Ни лишних слов, ни пропущенных.

   Слоты делай по грамматическим решениям: подлежащее, вспомогательный глагол,
   форма смыслового глагола. Хвост предложения, где выбирать нечего, клади
   одним слотом с одним-двумя вариантами.

   options должны быть из одной парадигмы: для "doesn't" это "don't/didn't/
   won't", для "works" это "work/worked/working". Не подсовывай варианты,
   очевидно неподходящие по части речи — иначе задание решается исключением.

5. Лексика уровня A1-A2. Никаких редких слов.

Отвечай строго JSON-массивом."""

SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "ru": {"type": "STRING"},
            "en": {"type": "STRING"},
            "alternatives": {"type": "ARRAY", "items": {"type": "STRING"}},
            "slots": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "correct": {"type": "STRING"},
                        "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["correct", "options"],
                },
            },
        },
        "required": ["ru", "en", "alternatives", "slots"],
    },
}

_PUNCT = re.compile(r"[.!?]+$")


def _norm(text: str) -> str:
    """Compare sentences without being derailed by spacing or a full stop."""
    return " ".join(_PUNCT.sub("", (text or "")).split()).lower()


def check(row: dict[str, Any], max_words: int = MAX_WORDS) -> list[str]:
    """Every reason this exercise is unusable. Empty list means it's good."""
    problems: list[str] = []
    ru = (row.get("ru") or "").strip()
    en = (row.get("en") or "").strip()
    slots = row.get("slots") or []

    if not ru:
        problems.append("пустое русское предложение")
    if not en:
        problems.append("пустой перевод")
        return problems

    n = len(en.split())
    if not (MIN_WORDS <= n <= max_words):
        problems.append(f"en длиной {n} слов, нужно {MIN_WORDS}-{max_words}")
    if re.search(r"[А-Яа-яЁё]", en):
        problems.append("в en есть кириллица")
    if not re.search(r"[А-Яа-яЁё]", ru):
        problems.append("ru не по-русски")

    if len(slots) < 2:
        problems.append("меньше двух слотов — собирать нечего")
        return problems

    # The whole point: the assembled slots must BE the answer. A mismatch means
    # the assisted mode would teach a different sentence from the typing mode.
    assembled = " ".join((s.get("correct") or "").strip() for s in slots)
    if _norm(assembled) != _norm(en):
        problems.append(f"склейка слотов «{assembled}» не совпадает с en «{en}»")

    for i, slot in enumerate(slots, 1):
        correct = (slot.get("correct") or "").strip()
        options = [o.strip() for o in (slot.get("options") or []) if o and o.strip()]
        if not correct:
            problems.append(f"слот {i}: пустой правильный вариант")
            continue
        if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
            problems.append(f"слот {i}: вариантов {len(options)}, нужно {MIN_OPTIONS}-{MAX_OPTIONS}")
        lowered = [o.lower() for o in options]
        if correct.lower() not in lowered:
            problems.append(f"слот {i}: среди вариантов нет правильного «{correct}»")
        if len(set(lowered)) != len(lowered):
            problems.append(f"слот {i}: варианты повторяются")
    return problems


def ask(
    model: str,
    key: str,
    spec: str,
    count: int,
    avoid: list[str],
    notes: list[str] | None = None,
    max_words: int = MAX_WORDS,
) -> list[dict[str, Any]]:
    lines = [f"Тема: {spec}", f"Сделай {count} заданий."]
    if max_words != MAX_WORDS:
        # The system prompt states the default; without this the model keeps
        # writing to nine words and everything longer is rejected as too long.
        lines.append(f"Для этой темы en может быть длиной до {max_words} слов.")
    if avoid:
        lines.append("Эти русские предложения уже есть, не повторяй их:")
        lines.append("; ".join(avoid[-60:]))
    for problem in notes or []:
        lines.append(f"ИСПРАВЬ В ПРОШЛЫЙ РАЗ БЫЛО: {problem}")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.8,  # variety matters; identical phrasings are useless
        },
    }
    rows = call(model, key, payload)
    return [r for r in rows if isinstance(r, dict)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, help="grammar_topics.slug")
    ap.add_argument("--spec", required=True, help="what the sentences must drill")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-words", type=int, default=MAX_WORDS)
    args = ap.parse_args()

    key = read_api_key()
    out_path = Path(args.out)
    done: list[dict[str, Any]] = []
    if out_path.exists():
        done = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"resuming — {len(done)} already generated")

    seen_ru = {_norm(r["ru"]) for r in done}
    rejected = 0
    stalled = 0

    while len(done) < args.count and stalled < 6:
        want = min(args.batch, args.count - len(done))
        try:
            rows = ask(args.model, key, args.spec, want, [r["ru"] for r in done], max_words=args.max_words)
        except RuntimeError as exc:
            print(f"  партия не удалась: {exc}")
            stalled += 1
            continue
        added = 0
        for row in rows:
            problems = check(row, args.max_words)
            if problems:
                rejected += 1
                continue
            key_ru = _norm(row["ru"])
            if key_ru in seen_ru:
                continue  # duplicate prompt, silently skipped
            seen_ru.add(key_ru)
            done.append(
                {
                    "topic": args.topic,
                    "ru": row["ru"].strip(),
                    "en": row["en"].strip(),
                    "alternatives": [a.strip() for a in row.get("alternatives", []) if a.strip()],
                    "slots": [
                        {
                            "correct": s["correct"].strip(),
                            "options": [o.strip() for o in s["options"] if o.strip()],
                        }
                        for s in row["slots"]
                    ],
                }
            )
            added += 1
        stalled = stalled + 1 if added == 0 else 0
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {len(done)}/{args.count} — принято {added}, отсеяно всего {rejected}")

    print(f"done: {len(done)} -> {out_path}")
    print(f"отсеяно автопроверками: {rejected}")


if __name__ == "__main__":
    main()
