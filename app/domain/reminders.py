from __future__ import annotations

from enum import StrEnum

# Pure decision logic for the reminder worker — no I/O, fully unit-tested.


class ReminderKind(StrEnum):
    STREAK = "streak"      # has a streak but hasn't studied today → don't lose it
    DAILY = "daily"        # daily goal not finished yet
    INACTIVE = "inactive"  # away for several days


def decide_reminder(
    *,
    studied_today: int,
    daily_goal: int,
    streak_days: int,
    days_since_study: int | None,
    local_hour: int,
    window_start: int,
    window_end: int,
) -> ReminderKind | None:
    """Returns which reminder to send now, or None.

    Only ever one reminder per call; the worker additionally enforces once-per-day
    per user via Redis. Sends only inside the local-time window.
    """
    if not (window_start <= local_hour < window_end):
        return None
    goal = max(1, daily_goal)
    if studied_today >= goal:
        return None  # goal met — don't nag
    if streak_days > 0 and studied_today == 0:
        return ReminderKind.STREAK
    if studied_today > 0:
        return ReminderKind.DAILY  # partial progress — nudge to finish
    if days_since_study is not None and days_since_study >= 3:
        return ReminderKind.INACTIVE
    return ReminderKind.DAILY  # nothing studied yet today, gentle nudge
