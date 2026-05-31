from __future__ import annotations

from app.domain.push import in_window, normalize_window, window_hours


def test_in_window_same_day():
    assert in_window(10, 10, 22) is True
    assert in_window(21, 10, 22) is True
    assert in_window(22, 10, 22) is False  # end exclusive
    assert in_window(9, 10, 22) is False


def test_in_window_overnight():
    # 22→08 active at 22, 23, 0..7
    assert in_window(22, 22, 8) is True
    assert in_window(23, 22, 8) is True
    assert in_window(0, 22, 8) is True
    assert in_window(7, 22, 8) is True
    assert in_window(8, 22, 8) is False  # end exclusive
    assert in_window(12, 22, 8) is False


def test_in_window_end_midnight():
    assert in_window(23, 14, 24) is True
    assert in_window(14, 14, 24) is True
    assert in_window(13, 14, 24) is False


def test_window_hours():
    assert window_hours(10, 22) == 12
    assert window_hours(22, 8) == 10   # overnight
    assert window_hours(14, 24) == 10
    assert window_hours(23, 9) == 10   # overnight
    assert window_hours(10, 10) == 0


def test_normalize_window_valid():
    assert normalize_window(8, 23, min_hours=10, default=(10, 22)) == (8, 23)


def test_normalize_window_overnight_ok():
    assert normalize_window(22, 8, min_hours=10, default=(10, 22)) == (22, 8)   # 10h overnight
    assert normalize_window(23, 9, min_hours=10, default=(10, 22)) == (23, 9)


def test_normalize_window_too_narrow_falls_back():
    assert normalize_window(10, 15, min_hours=10, default=(10, 22)) == (10, 22)
    assert normalize_window(22, 7, min_hours=10, default=(10, 22)) == (10, 22)  # 9h overnight < 10


def test_normalize_window_invalid_falls_back():
    assert normalize_window(-1, 10, min_hours=10, default=(10, 22)) == (10, 22)
    assert normalize_window(0, 24, min_hours=10, default=(10, 22)) == (10, 22)  # 24h not allowed
