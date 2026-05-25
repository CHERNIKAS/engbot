from __future__ import annotations

from app.domain.models import UserWord, Word
from app.infrastructure.repositories.user_words import _pick_avoiding


def _row(uw_id: int) -> tuple[UserWord, Word]:
    return UserWord(id=uw_id), Word(id=uw_id)


def test_pick_avoiding_skips_the_just_answered_card():
    """With alternatives present, the excluded (last-shown) word is never picked."""
    rows = [_row(42), _row(7), _row(9)]
    for _ in range(20):
        uw, _w = _pick_avoiding(rows, exclude_uw_id=42)
        assert uw.id != 42


def test_pick_avoiding_returns_excluded_when_its_the_only_one():
    """A user with a single active word still gets a card (can't avoid a repeat)."""
    rows = [_row(42)]
    uw, _w = _pick_avoiding(rows, exclude_uw_id=42)
    assert uw.id == 42


def test_pick_avoiding_empty_is_none():
    assert _pick_avoiding([], exclude_uw_id=42) is None


def test_pick_avoiding_no_exclusion_returns_first():
    rows = [_row(5), _row(6)]
    uw, _w = _pick_avoiding(rows, exclude_uw_id=0)
    assert uw.id == 5
