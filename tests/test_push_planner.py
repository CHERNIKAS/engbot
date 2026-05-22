from __future__ import annotations

from app.domain.push import in_window, normalize_window


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
