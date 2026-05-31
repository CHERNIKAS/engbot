from __future__ import annotations

# Pure helpers for push-learning windows. No I/O — unit-tested. Card selection
# itself (new / repeat / mastered-review) lives in PushService.run_tick.
#
# A window is [start, end) in local hours. It may wrap past midnight: when
# end <= start the window runs overnight (e.g. 22→8 is active at 22, 23, 0..7).
# `end` may be 24 (midnight) for an evening window that ends exactly at 00:00.


def window_hours(start: int, end: int) -> int:
    """Length of the window in hours, wrapping past midnight. 0 if start==end."""
    if start == end:
        return 0
    if end > start:
        return end - start
    return 24 - start + end  # overnight (end < start)


def in_window(local_hour: int, start: int, end: int) -> bool:
    """Whether the local hour is inside [start, end), wrapping past midnight."""
    if start == end:
        return False
    if end > start:  # same day (includes end == 24)
        return start <= local_hour < end
    return local_hour >= start or local_hour < end  # overnight


def normalize_window(start: int, end: int, *, min_hours: int, default: tuple[int, int]) -> tuple[int, int]:
    """Clamp a user-chosen window to a valid span (overnight allowed) of at least
    min_hours and under 24h. Falls back to `default` if out of range/too short."""
    if not (0 <= start <= 23 and 0 < end <= 24):
        return default
    hours = window_hours(start, end)
    if not (min_hours <= hours < 24):
        return default
    return start, end
