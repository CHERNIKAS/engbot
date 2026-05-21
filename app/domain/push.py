from __future__ import annotations

# Pure scheduling logic for push-learning. No I/O — fully unit-tested.
# The service computes the boolean inputs (from Redis state + clock) and acts on
# the returned decision.

# Decisions:
#   "retry"  — re-send the current (ignored) in-flight card
#   "wait"   — do nothing this tick
#   "repeat" — push a same-day repeat of an already-answered word
#   "new"    — push a new word (daily new-quota not exhausted)
#   "idle"   — nothing left to push right now


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


def plan_next(
    *,
    in_window_now: bool,
    has_inflight: bool,
    inflight_retry_due: bool,
    gap_due: bool,
    repeat_due: bool,
    new_allowed: bool,
) -> str:
    if not in_window_now:
        return "wait"
    if has_inflight:
        return "retry" if inflight_retry_due else "wait"
    if not gap_due:
        return "wait"
    if repeat_due:
        return "repeat"
    if new_allowed:
        return "new"
    return "idle"
