"""Every construction exercise, checked against the rules it has to obey.

The assisted mode and the typing mode read the same row: one shows `slots`, the
other checks against `en`. If those two disagree the learner is taught one
sentence and graded on another, and nothing at runtime would notice — the
assembled tiles would simply be wrong, every time, for that one exercise.

So the whole set is verified here rather than sampled.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "versions"
    / "0055_present_simple_constructor.py"
)
_spec = importlib.util.spec_from_file_location("m0055", _MIGRATION)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)

PHRASES = _m.PHRASES
_PUNCT = re.compile(r"[.!?]+$")


def _norm(text: str) -> str:
    return " ".join(_PUNCT.sub("", text).split()).lower()


def test_the_set_is_the_size_it_claims():
    assert len(PHRASES) == 100


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_slots_assemble_into_the_answer(ru, en, alts, slots):
    """The one invariant the two modes share. A mismatch here means the tiles
    build a sentence the checker will reject."""
    assembled = " ".join(s["correct"] for s in slots)
    assert _norm(assembled) == _norm(en), f"«{ru}»: собралось «{assembled}», ждали «{en}»"


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_every_slot_offers_its_own_answer(ru, en, alts, slots):
    """Otherwise the exercise is unsolvable in the assisted mode."""
    for i, slot in enumerate(slots, 1):
        options = [o.lower() for o in slot["options"]]
        assert slot["correct"].lower() in options, f"«{ru}» слот {i}"
        assert len(set(options)) == len(options), f"«{ru}» слот {i}: повторы"
        assert 2 <= len(options) <= 4, f"«{ru}» слот {i}: вариантов {len(options)}"


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_there_is_something_to_decide(ru, en, alts, slots):
    """A single slot is not construction, it is a multiple-choice card wearing
    a different name."""
    assert len(slots) >= 2, f"«{ru}»: слотов {len(slots)}"


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_the_prompt_is_russian_and_the_answer_is_not(ru, en, alts, slots):
    assert re.search(r"[А-Яа-яЁё]", ru), ru
    assert not re.search(r"[А-Яа-яЁё]", en), en


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_alternatives_never_repeat_the_main_answer(ru, en, alts, slots):
    """A duplicate would make the checker's accepted set look wider than it is."""
    assert _norm(en) not in {_norm(a) for a in alts}, ru


def test_prompts_are_unique():
    """Two exercises with the same Russian are one exercise and a wasted slot
    in the learner's day."""
    seen = [_norm(ru) for ru, *_ in PHRASES]
    assert len(set(seen)) == len(seen)


def test_all_three_forms_of_the_tense_are_drilled():
    """A Present Simple set that is all affirmatives teaches half the tense —
    and the half a Russian speaker already guesses right."""
    questions = sum(1 for _ru, en, *_ in PHRASES if en.lower().startswith(("do ", "does ")))
    negatives = sum(
        1 for _ru, en, *_ in PHRASES
        if any(n in en.lower() for n in ("don't", "doesn't", "do not", "does not"))
    )
    assert questions >= 20, questions
    assert negatives >= 20, negatives


def test_third_person_singular_is_well_represented():
    """`-s` is the error Russian speakers actually make; a set that avoids it
    would pass everyone while teaching nothing."""
    third = sum(
        1 for _ru, en, *_ in PHRASES
        if re.search(r"\b(he|she|it|does|doesn't)\b", en.lower())
    )
    assert third >= 40, third


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_the_checker_accepts_what_the_slots_build(ru, en, alts, slots):
    """The generator and the checker were written apart, so nothing guaranteed
    they agree. If they do not, the assisted mode walks the learner to an
    answer the typing mode rejects — and it would look like the learner's
    mistake, on every single attempt."""
    from app.domain.constructor import full_answer, matches

    assert matches(full_answer(slots), en, alts), ru


@pytest.mark.parametrize("ru,en,alts,slots", PHRASES)
def test_the_checker_accepts_every_alternative_we_ship(ru, en, alts, slots):
    """An alternative the checker rejects is worse than no alternative: the
    learner is told a correct sentence is wrong."""
    from app.domain.constructor import matches

    for alt in alts:
        assert matches(alt, en, alts), f"{ru}: «{alt}»"
