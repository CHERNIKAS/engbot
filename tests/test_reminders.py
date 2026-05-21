from __future__ import annotations

from app.domain.reminders import ReminderKind, decide_reminder

# In-window defaults (window 19:00–22:00).
W = {"local_hour": 20, "window_start": 19, "window_end": 22}


def test_outside_window_is_none():
    assert (
        decide_reminder(
            studied_today=0,
            daily_goal=10,
            streak_days=3,
            days_since_study=1,
            local_hour=9,
            window_start=19,
            window_end=22,
        )
        is None
    )


def test_goal_met_is_none():
    assert decide_reminder(studied_today=10, daily_goal=10, streak_days=3, days_since_study=0, **W) is None


def test_streak_at_risk():
    assert (
        decide_reminder(studied_today=0, daily_goal=10, streak_days=4, days_since_study=1, **W)
        == ReminderKind.STREAK
    )


def test_partial_progress_is_daily():
    assert (
        decide_reminder(studied_today=3, daily_goal=10, streak_days=0, days_since_study=0, **W)
        == ReminderKind.DAILY
    )


def test_inactive_after_three_days():
    assert (
        decide_reminder(studied_today=0, daily_goal=10, streak_days=0, days_since_study=5, **W)
        == ReminderKind.INACTIVE
    )


def test_new_user_gentle_daily():
    assert (
        decide_reminder(studied_today=0, daily_goal=10, streak_days=0, days_since_study=None, **W)
        == ReminderKind.DAILY
    )


def test_zero_goal_clamped_to_one():
    assert decide_reminder(studied_today=1, daily_goal=0, streak_days=0, days_since_study=0, **W) is None
