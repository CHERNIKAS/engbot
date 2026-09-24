"""Boundaries a mutation run proved nothing was checking.

Mutating `app/domain` produced 655 mutants and the suite killed 587. Most
survivors turned out to be equivalent — `excess <= 0` against `excess < 0`
where both paths return 0, or a branch already guarded above it. These are the
ones that were not: each mutant below changes what the bot decides about a
learner, and every existing test passed with the change in place.
"""
from __future__ import annotations

from app.domain.levels import DEMOTE_ACCURACY, DEMOTE_MIN_ATTEMPTS, recalibrated_level
from app.domain.mastery import RECOGNITION, apply_credit
from app.domain.themes import THEMES, position_of


def test_demotion_needs_accuracy_strictly_below_the_bar():
    """`accuracy < DEMOTE_ACCURACY` survived being flipped to `<=`, so nothing
    pinned the edge. It decides whether a user is moved down a level, and a
    learner sitting exactly on the bar should be left alone — demotion is meant
    to be harder to trigger than promotion, not to fire on a tie."""
    attempts = DEMOTE_MIN_ATTEMPTS
    exactly_on_bar = round(attempts * DEMOTE_ACCURACY)
    assert recalibrated_level("B1", 0, attempts, exactly_on_bar) is None
    assert recalibrated_level("B1", 0, attempts, exactly_on_bar - 1) == "A2"


def test_score_is_rounded_to_two_decimals():
    """The rounding precision survived being changed from 2 to 3. It is the
    stored shape of every learning score, and the mastery bars are written to
    two decimals — a third one only accumulates noise the targets never expect."""
    score = apply_credit(0.0, RECOGNITION)
    assert score == 0.5
    drifted = 0.0
    for _ in range(3):
        drifted = apply_credit(drifted, RECOGNITION)
    assert drifted == 1.5
    assert repr(apply_credit(0.005, RECOGNITION)) == repr(0.51)


def test_theme_order_follows_the_declared_sequence():
    """`position_of` had no test at all. It is the teaching order of the whole
    thematic curriculum: numbers and colours before hotels and technology."""
    assert position_of(THEMES[0].slug) == 0
    assert position_of(THEMES[-1].slug) == len(THEMES) - 1
    assert position_of("numbers") < position_of("hotel")


def test_an_unknown_theme_sorts_last_instead_of_raising():
    """A pack naming a theme that was later removed must not take the menu down
    with it."""
    assert position_of("no-such-theme") == len(THEMES)
