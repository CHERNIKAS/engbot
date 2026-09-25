"""The teaching order of the grammar topics, pinned.

This exists because the order has already drifted once without anyone
noticing. Migration 0054 inserted two topics with
`UPDATE ... SET position = position + 1 WHERE position >= :pos`, and every
position recorded anywhere else silently became wrong by two — which is how
`did` ended up twelve topics behind the tense that needs it.

A note in a handoff file decays the same way. This does not: the expected
sequence is written out here, and the next shift fails the suite instead of
reaching a learner.

The rule the list encodes: no topic appears before what it stands on.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0059_grammar_order.py"

EXPECTED = [
    "tense_present_simple",
    "verb_to_be",
    "do_does_questions",
    "tense_present_continuous",
    "tense_past_simple",
    "irregular_past",
    "was_were",
    "questions_word_order",
    "plurals_basic",
    "quantifiers_basic",
    "articles_basic",
    "prepositions_basic",
    "comparatives",
    "tense_future_will",
    "future_going_to",
    "modals_basic",
    "past_continuous",
    "irregular_participle",
    "present_perfect",
    "past_perfect",
    "present_perfect_continuous",
    "used_to",
    "gerund_infinitive",
    "conditionals_01",
    "conditional_second",
    "conditional_third",
    "passive_simple",
    "reported_speech",
    "relative_clauses",
    "tag_questions",
]


def _migration():
    spec = importlib.util.spec_from_file_location("m0059", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_curriculum_order_is_what_was_agreed():
    assert _migration().ORDER == EXPECTED


def test_every_topic_appears_exactly_once():
    """A slug listed twice would assign two positions and the last one would
    win silently, putting a topic somewhere nobody chose."""
    order = _migration().ORDER
    assert len(order) == len(set(order)) == 30


def test_nothing_is_taught_before_what_it_stands_on():
    """The dependencies that were actually broken before, written as pairs.

    `did` sat at 14 while Past Simple sat at 2, so for twelve topics a learner
    knew `went` and could not ask «Did you go?». The questions forms must
    follow the statement they invert, and the irregular forms must follow the
    tense that needs them.
    """
    at = {slug: i for i, slug in enumerate(_migration().ORDER)}
    depends_on = [
        ("do_does_questions", "tense_present_simple"),
        ("questions_word_order", "tense_past_simple"),
        ("was_were", "verb_to_be"),
        ("was_were", "tense_past_simple"),
        ("irregular_past", "tense_past_simple"),
        ("irregular_participle", "tense_past_simple"),
        ("present_perfect", "irregular_participle"),
        ("past_perfect", "present_perfect"),
        ("present_perfect_continuous", "present_perfect"),
        ("conditional_second", "conditionals_01"),
        ("conditional_third", "conditional_second"),
        ("future_going_to", "tense_future_will"),
        ("comparatives", "plurals_basic"),
    ]
    for later, earlier in depends_on:
        assert at[later] > at[earlier], f"{later} is taught before {earlier}"


def test_the_three_new_topics_land_in_the_first_third():
    """They fill gaps a beginner hits immediately — `to be` and `do/does` are
    needed by the very first tense, `was/were` by the first past one. Placed
    late they would be a reference nobody reaches in time."""
    at = {slug: i for i, slug in enumerate(_migration().ORDER)}
    for slug in ("verb_to_be", "do_does_questions", "was_were"):
        assert at[slug] < 10


def test_renaming_keeps_the_slug_so_progress_is_not_orphaned():
    """The topic is narrowed in place, not replaced. A new slug would strand
    whatever `user_grammar_topics` rows point at the old one."""
    module = _migration()
    assert module.RENAMED["slug"] == "questions_word_order"
    assert "questions_word_order" in module.ORDER


def test_downgrade_restores_the_original_title_and_rule():
    """A downgrade that leaves the topic titled «Вопросы в прошлом: did» while
    it holds the old mixed exercises describes something it does not teach."""
    old = _migration().RENAMED_OLD
    assert old["title"] == "Вопросы и порядок слов"
    assert "порядок" in old["rule"]
