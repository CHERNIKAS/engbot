"""Leech detection: a word missed LEECH_THRESHOLD times in a row triggers the
'postpone?' offer; any correct answer resets the streak; mastered words never
become leeches."""
from __future__ import annotations

from app.services.push_service import LEECH_THRESHOLD, _leech_after


def test_streak_increments_on_wrong():
    n, leech = _leech_after(0, correct=False, was_mastered=False)
    assert n == 1 and leech is False
    n, leech = _leech_after(4, correct=False, was_mastered=False)
    assert n == 5 and leech is False


def test_triggers_exactly_at_threshold():
    n, leech = _leech_after(LEECH_THRESHOLD - 1, correct=False, was_mastered=False)
    assert n == LEECH_THRESHOLD and leech is True


def test_stays_triggered_past_threshold():
    n, leech = _leech_after(LEECH_THRESHOLD + 2, correct=False, was_mastered=False)
    assert n == LEECH_THRESHOLD + 3 and leech is True


def test_correct_resets_streak_and_never_leeches():
    n, leech = _leech_after(5, correct=True, was_mastered=False)
    assert n == 0 and leech is False


def test_mastered_word_never_becomes_leech():
    """A mastered word answered wrong rides its 0–5 score, not the leech track."""
    n, leech = _leech_after(99, correct=False, was_mastered=True)
    assert n == 0 and leech is False


def test_none_counter_is_treated_as_zero():
    n, leech = _leech_after(None, correct=False, was_mastered=False)  # type: ignore[arg-type]
    assert n == 1 and leech is False
