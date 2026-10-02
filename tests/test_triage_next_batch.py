"""Knowing most of a triage screen brings the next one at once.

The owner, 2026-10-02: marked all fifteen of a screen as known, and then the
rest of the theme — just as basic — came one card at a time, because the plan
holds a single triage slot a day.
"""
from __future__ import annotations

from app.domain import triage


def test_most_of_a_full_screen_known_asks_for_more():
    assert triage.wants_another(15, 15)
    assert triage.wants_another(12, 15)
    assert not triage.wants_another(11, 15)


def test_a_short_last_screen_uses_the_same_share():
    assert triage.wants_another(8, 10)
    assert not triage.wants_another(7, 10)


def test_nothing_offered_asks_for_nothing():
    assert not triage.wants_another(0, 0)
