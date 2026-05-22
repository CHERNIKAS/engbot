from __future__ import annotations

# Pure helpers for push-learning windows. No I/O — unit-tested. Card selection
# itself (new / repeat / mastered-review) lives in PushService.run_tick.


def in_window(local_hour: int, start: int, end: int) -> bool:
    """Whether the local hour is inside the (same-day) push window [start, end)."""
    return start <= local_hour < end


def normalize_window(start: int, end: int, *, min_hours: int, default: tuple[int, int]) -> tuple[int, int]:
    """Clamp a user-chosen window to a valid same-day span of at least min_hours."""
    if not (0 <= start <= 23 and 0 < end <= 24 and start < end):
        return default
    if end - start < min_hours:
        return default
    return start, end
