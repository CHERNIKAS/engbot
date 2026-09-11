"""Which stored push windows are accepted as they are.

normalize_window guards push_ws / push_we read back from settings. The
property test only checked the resulting length, so every range bound
survived mutation: start 24 or end 25 would be taken as given, and a
midnight start (0) could be silently reset to the default.
"""
from __future__ import annotations

from app.domain.push import normalize_window

DEFAULT = (10, 22)


def _n(start: int, end: int) -> tuple[int, int]:
    return normalize_window(start, end, min_hours=5, default=DEFAULT)


def test_every_edge_hour_the_picker_offers_is_accepted():
    """The start grid offers 00..23 and the end grid 01..24."""
    assert _n(0, 8) == (0, 8)  # a midnight start
    assert _n(16, 24) == (16, 24)  # ends exactly at midnight
    assert _n(23, 6) == (23, 6)  # the latest start, overnight
    assert _n(19, 1) == (19, 1)  # the earliest end, overnight


def test_hours_off_the_clock_fall_back_to_the_default():
    assert _n(24, 5) == DEFAULT
    assert _n(-1, 8) == DEFAULT
    assert _n(5, 25) == DEFAULT
    assert _n(5, 0) == DEFAULT  # midnight as an end is 24, never 0
