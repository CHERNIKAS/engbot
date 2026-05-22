from __future__ import annotations

import random

import pytest

from app.domain.push_nudges import CHEEKY, DRAMATIC, GENTLE, nudge_line


@pytest.mark.parametrize(
    "attempts,pool",
    [
        (1, GENTLE),
        (2, GENTLE),
        (3, CHEEKY),
        (5, CHEEKY),
        (6, DRAMATIC),
        (12, DRAMATIC),
    ],
)
def test_nudge_tier_by_attempts(attempts: int, pool: tuple[str, ...]):
    line = nudge_line(attempts, rng=random.Random(0))
    phrase = line.split("\n", 1)[0]
    assert phrase in pool


def test_nudge_includes_repeat_count():
    assert "повтор №1" in nudge_line(1, rng=random.Random(1))
    assert "повтор №7" in nudge_line(7, rng=random.Random(1))


def test_nudge_floor_is_one():
    # 0 / negative attempts shouldn't crash or show "№0".
    assert "повтор №1" in nudge_line(0, rng=random.Random(2))


def test_nudge_is_deterministic_with_seed():
    a = nudge_line(4, rng=random.Random(42))
    b = nudge_line(4, rng=random.Random(42))
    assert a == b
