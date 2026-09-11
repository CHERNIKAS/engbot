"""Product constants of the pace screen, pinned by value.

Mutation testing found both of these free to change without a single test
failing, because every existing check compared against the constant itself.
"""
from __future__ import annotations

from app.domain.pacing import label_for, overflow, pace_of


def test_a_new_user_starts_on_the_steady_pace():
    """DEFAULT_PACE 7 to 8 survived: a new user would see a bare 8 in
    settings instead of the named option."""
    assert pace_of({}) == 7
    assert pace_of(None) == 7
    assert label_for(pace_of({})) == "🚶 Ровно"


def test_an_offer_appears_at_exactly_the_threshold():
    """excess >= 5 to excess > 5 survived. Ceiling 30 puts the target at 24,
    so 29 active words are five over it, below the ceiling: that is the
    smallest offer worth making, and 28 is one short of it."""
    assert overflow(29, 30) == 5
    assert overflow(28, 30) == 0
