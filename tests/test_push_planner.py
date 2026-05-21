from __future__ import annotations

from app.domain.push import in_window, normalize_window, plan_next


def test_in_window():
    assert in_window(10, 10, 22) is True
    assert in_window(21, 10, 22) is True
    assert in_window(22, 10, 22) is False  # end exclusive
    assert in_window(9, 10, 22) is False


def test_normalize_window_valid():
    assert normalize_window(8, 23, min_hours=10, default=(10, 22)) == (8, 23)


def test_normalize_window_too_narrow_falls_back():
    assert normalize_window(10, 15, min_hours=10, default=(10, 22)) == (10, 22)


def test_normalize_window_invalid_falls_back():
    assert normalize_window(22, 6, min_hours=10, default=(10, 22)) == (10, 22)  # crosses midnight
    assert normalize_window(-1, 10, min_hours=10, default=(10, 22)) == (10, 22)


def test_plan_wait_outside_window():
    assert plan_next(
        in_window_now=False, has_inflight=True, inflight_retry_due=True,
        gap_due=True, repeat_due=True, new_allowed=True,
    ) == "wait"


def test_plan_retry_when_inflight_due():
    assert plan_next(
        in_window_now=True, has_inflight=True, inflight_retry_due=True,
        gap_due=True, repeat_due=True, new_allowed=True,
    ) == "retry"


def test_plan_wait_when_inflight_not_due():
    assert plan_next(
        in_window_now=True, has_inflight=True, inflight_retry_due=False,
        gap_due=True, repeat_due=True, new_allowed=True,
    ) == "wait"


def test_plan_wait_when_gap_not_due():
    assert plan_next(
        in_window_now=True, has_inflight=False, inflight_retry_due=False,
        gap_due=False, repeat_due=True, new_allowed=True,
    ) == "wait"


def test_plan_repeat_before_new():
    assert plan_next(
        in_window_now=True, has_inflight=False, inflight_retry_due=False,
        gap_due=True, repeat_due=True, new_allowed=True,
    ) == "repeat"


def test_plan_new_when_no_repeat():
    assert plan_next(
        in_window_now=True, has_inflight=False, inflight_retry_due=False,
        gap_due=True, repeat_due=False, new_allowed=True,
    ) == "new"


def test_plan_idle_when_nothing_left():
    assert plan_next(
        in_window_now=True, has_inflight=False, inflight_retry_due=False,
        gap_due=True, repeat_due=False, new_allowed=False,
    ) == "idle"
