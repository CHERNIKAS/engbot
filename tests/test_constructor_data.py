"""Every generated construction phrase, checked before it can reach a learner.

`tests/test_constructor_phrases.py` does this for the hundred Present Simple
phrases written into migration 0055. This does the same for everything in
`app/infrastructure/data/constructor/`, which migration 0060 inserts.

The invariant that matters is the first one: the assisted mode builds the
sentence out of `slots` and the typing mode grades against `en`. When those
disagree, the learner taps the only path the card offers, is told they are
wrong, and nothing at runtime notices — so the whole set is verified here
rather than sampled.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import pytest

DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "app" / "infrastructure" / "data" / "constructor"
)

_PUNCT = re.compile(r"[.!?]+$")


def _norm(text: str) -> str:
    return " ".join(_PUNCT.sub("", text).split()).lower()


def _load() -> list[tuple[str, dict]]:
    if not DATA_DIR.exists():
        return []
    out: list[tuple[str, dict]] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            out.append((path.stem, row))
    return out


PHRASES = _load()
FILES = sorted(DATA_DIR.glob("*.json")) if DATA_DIR.exists() else []


def _ids(items):
    return [f"{slug}-{i}" for i, (slug, _row) in enumerate(items)]


@pytest.mark.skipif(not PHRASES, reason="no generated phrases yet")
@pytest.mark.parametrize("slug,row", PHRASES, ids=_ids(PHRASES))
def test_slots_assemble_into_the_answer(slug, row):
    """A mismatch here teaches one sentence and grades another."""
    assembled = " ".join(s["correct"] for s in row["slots"])
    assert _norm(assembled) == _norm(row["en"]), (
        f"{slug}: «{row['ru']}» собралось «{assembled}», ждали «{row['en']}»"
    )


@pytest.mark.skipif(not PHRASES, reason="no generated phrases yet")
@pytest.mark.parametrize("slug,row", PHRASES, ids=_ids(PHRASES))
def test_every_slot_offers_its_own_answer(slug, row):
    """Otherwise the exercise cannot be solved in the assisted mode at all."""
    for i, slot in enumerate(row["slots"]):
        assert slot["correct"] in slot["options"], f"{slug}: слот {i} без своего ответа"


@pytest.mark.skipif(not PHRASES, reason="no generated phrases yet")
@pytest.mark.parametrize("slug,row", PHRASES, ids=_ids(PHRASES))
def test_a_slot_is_a_choice(slug, row):
    """One option is not a decision — it is a tile that taps itself."""
    for i, slot in enumerate(row["slots"]):
        assert len(slot["options"]) >= 2, f"{slug}: слот {i} с одним вариантом"
        assert len(slot["options"]) == len(set(slot["options"])), (
            f"{slug}: слот {i} повторяет вариант"
        )


@pytest.mark.skipif(not PHRASES, reason="no generated phrases yet")
@pytest.mark.parametrize("slug,row", PHRASES, ids=_ids(PHRASES))
def test_both_sides_are_present(slug, row):
    assert row["ru"].strip()
    assert row["en"].strip()
    assert row["slots"]


@pytest.mark.skipif(not FILES, reason="no generated phrases yet")
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_a_topic_does_not_repeat_itself(path):
    """A repeated Russian sentence is a wasted slot in the day and reads as a
    bug to the learner, who has just answered it."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    seen = [_norm(r["ru"]) for r in rows]
    duplicates = {s for s in seen if seen.count(s) > 1}
    assert not duplicates, f"{path.stem}: повторы — {sorted(duplicates)[:5]}"


# Topics whose subject *is* the three forms — their specs demand affirmative,
# negative and question alike. Articles, plurals, prepositions and comparatives
# are left out on purpose: a question is not part of what they teach, and
# demanding one would push the generator into contortions.
FORM_DRIVEN = {
    "verb_to_be",
    "do_does_questions",
    "tense_present_continuous",
    "tense_past_simple",
    "irregular_past",
    "was_were",
    "questions_word_order",
    "tense_future_will",
    "future_going_to",
    "past_continuous",
    "present_perfect",
    "past_perfect",
    "present_perfect_continuous",
    "used_to",
    "passive_simple",
}

FORM_FILES = [p for p in FILES if p.stem in FORM_DRIVEN]


@pytest.mark.skipif(not FILES, reason="no generated phrases yet")
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_a_topic_is_not_one_sentence_a_hundred_times(path):
    """Lexically rich and structurally identical is still a degenerate set.

    The first `relative_clauses` run had 122 distinct words and 95% of its
    phrases opened «This is the …» — a learner drilling one frame a hundred
    times learns that frame, not the rule. Half is a loose ceiling on purpose:
    conditionals genuinely all start with «If I …», and that is the grammar,
    not a rut.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    if len(rows) < 20:
        pytest.skip("partial set")
    openings = collections.Counter(" ".join(r["en"].split()[:3]).lower() for r in rows)
    top, count = openings.most_common(1)[0]
    assert count <= len(rows) // 2, (
        f"{path.stem}: {count} из {len(rows)} начинаются с «{top}»"
    )


@pytest.mark.skipif(not FORM_FILES, reason="no generated phrases yet")
@pytest.mark.parametrize("path", FORM_FILES, ids=lambda p: p.stem)
def test_a_topic_drills_more_than_statements(path):
    """The set degenerating into affirmatives is the failure mode of every
    generated batch: it is half the forms, and the half a Russian speaker
    already guesses. Questions and negatives are where a tense is actually
    known or not."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    if len(rows) < 20:
        pytest.skip("partial set")
    questions = sum(1 for r in rows if r["en"].rstrip().endswith("?"))
    negatives = sum(1 for r in rows if "n't" in r["en"] or " not" in r["en"])
    assert questions >= len(rows) // 10, f"{path.stem}: вопросов всего {questions}"
    assert negatives >= len(rows) // 10, f"{path.stem}: отрицаний всего {negatives}"
