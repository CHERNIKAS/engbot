"""The content itself, against what a card needs and what Telegram accepts.

Runs on the restored copy, so it checks what learners actually get — 3000
constructor sentences and 30 rule tables written by generation passes, any one
of which can carry a slot whose right answer is not among its options (the
card can never be completed) or a table line too wide for a phone.
"""
from __future__ import annotations

import re

from tests.e2e.harness import telegram_problems

PRE_WIDTH = 32  # what a phone shows in <pre> without wrapping


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _sentence(s: str) -> str:
    """For comparing a built sentence: slots carry no final stop."""
    return _norm(s).rstrip(".?!")


async def test_every_constructor_slot_can_be_answered(h):
    rows = await h.sql("select id, en, slots from grammar_phrases")
    assert len(rows) > 100
    broken = []
    for pid, en, slots in rows:
        if not slots:
            continue  # typing-only sentence
        for i, slot in enumerate(slots):
            options = [_norm(o) for o in slot.get("options") or []]
            correct = _norm(slot.get("correct") or "")
            if not correct or correct not in options:
                broken.append(f"phrase {pid} slot {i}: correct {slot.get('correct')!r} not in {slot.get('options')}")
            elif len(set(options)) != len(options):
                broken.append(f"phrase {pid} slot {i}: duplicate options {slot.get('options')}")
            elif len(options) < 2:
                broken.append(f"phrase {pid} slot {i}: nothing to choose from {slot.get('options')}")
    assert broken == [], f"{len(broken)} broken slots:\n" + "\n".join(broken[:30])


async def test_assembled_slots_spell_the_sentence(h):
    """What the learner builds tap by tap is what the result card says was
    right; if they differ, a fully correct build is shown a different answer."""
    rows = await h.sql("select id, en, slots from grammar_phrases where jsonb_array_length(slots) > 0")
    off = []
    for pid, en, slots in rows:
        built = _sentence(" ".join(s.get("correct") or "" for s in slots))
        if built != _sentence(en):
            off.append(f"phrase {pid}: built {built!r} vs en {en!r}")
    assert off == [], f"{len(off)} phrases:\n" + "\n".join(off[:30])


async def test_rule_tables_fit_a_phone_and_parse(h):
    rows = await h.sql("select id, title, coalesce(rule, '') from grammar_topics")
    problems = []
    for tid, title, rule in rows:
        problems += [f"topic {tid} {title}: {p}" for p in telegram_problems(rule, None, "HTML")]
        for block in re.findall(r"<pre>(.*?)</pre>", rule, flags=re.S):
            for line in block.splitlines():
                if len(line) > PRE_WIDTH:
                    problems.append(f"topic {tid} {title}: <pre> line {len(line)} > {PRE_WIDTH}: {line!r}")
    assert problems == [], "\n".join(problems)
