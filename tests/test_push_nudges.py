"""The nudge pool: one voice, three temperatures, and the lines it must not cross.

Two pools were removed to get here, and the tests remember why. `DRAMATIC`
threatened to block people and taught them to block first — two of eight users
on production still sit with `push_blocked`. `GENTLE` was syrup («🌸 Загляни —
слово соскучилось») that nobody answered. Neither is allowed back, and the
checks below are what stops a future pass from reinventing either one.
"""
from __future__ import annotations

import random

import pytest

from app.domain.push_nudges import BLEAK, GRAVE, SNARKY, nudge_line

ALL = (*SNARKY, *BLEAK, *GRAVE)


@pytest.mark.parametrize(
    "attempts,pool",
    [
        (1, SNARKY),
        (2, BLEAK),
        (3, GRAVE),
        (9, GRAVE),
    ],
)
def test_the_tier_follows_the_attempt(attempts: int, pool: tuple[str, ...]):
    """Escalation is by heat, not by politeness: snide, then falling apart,
    then reporting from its own grave."""
    phrase = nudge_line(attempts, rng=random.Random(0)).split("\n", 1)[0]
    assert phrase in pool


def test_the_pool_is_large_enough_not_to_repeat_within_a_day():
    """A card is nudged three times and the day holds many cards, so a small
    pool means the same joke twice an evening — which stops being a joke."""
    assert len(ALL) >= 100


def test_no_line_appears_twice():
    assert len(set(ALL)) == len(ALL)


def test_nothing_threatens_the_user():
    """The removed `DRAMATIC` pool promised to block, to haunt, to come back in
    dreams. It measurably worked: people blocked the bot instead."""
    joined = " ".join(ALL).lower()
    for banned in ("заблокир", "во снах", "преследу", "сопротивлен", "удалю", "больше не приду"):
        assert banned not in joined, banned


def test_the_joke_is_about_the_bot_not_about_the_person():
    """The one boundary that matters. The bot may sulk, rot and die; it may not
    call the learner names, and it may not touch health, family, money or work
    — places where a joke stops being one."""
    joined = " ".join(ALL).lower()
    for banned in (
        "неудачник", "тупой", "дебил", "идиот", "дурак", "ничтожеств",
        "болен", "болезн", "умрёшь", "сдохн",
        "мать", "отец", "жена", "муж", "ребёнок",
        "зарплат", "долг", "кредит", "уволь", "нищ",
    ):
        assert banned not in joined, banned


def test_every_line_says_something():
    for line in ALL:
        assert line.strip()
        assert len(line) <= 120, line  # a nudge rides on top of a card


def test_the_repeat_count_is_always_shown():
    """It is the only informative part of the line: it tells the learner this
    is the same card, not a new one — the distinction a user asked about."""
    assert "повтор №1" in nudge_line(1, rng=random.Random(1))
    assert "повтор №7" in nudge_line(7, rng=random.Random(1))


def test_the_count_never_reads_zero():
    assert "повтор №1" in nudge_line(0, rng=random.Random(2))
    assert "повтор №1" in nudge_line(-5, rng=random.Random(2))


def test_a_high_attempt_count_does_not_fall_off_the_tiers():
    """`PUSH_MAX_ATTEMPTS` drops a card after a few nudges, but nothing here
    may depend on that — a changed limit must not start raising IndexError."""
    for attempts in (1, 2, 3, 4, 50, 10_000):
        assert nudge_line(attempts, rng=random.Random(7))


def test_the_same_seed_gives_the_same_line():
    assert nudge_line(4, rng=random.Random(42)) == nudge_line(4, rng=random.Random(42))
