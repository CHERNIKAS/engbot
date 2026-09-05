from __future__ import annotations

from app.domain.pacing import (
    DEFAULT_PACE,
    MAX_POOL,
    MIN_POOL,
    PACE_VALUES,
    ceiling_of,
    label_for,
    pace_of,
    overflow,
    pool_ceiling,
)


def test_pace_of_default_when_unset():
    assert pace_of({}) == DEFAULT_PACE
    assert pace_of(None) == DEFAULT_PACE


def test_pace_of_reads_valid_value():
    assert pace_of({"new_pace": 15}) == 15
    assert pace_of({"new_pace": 3}) == 3


def test_pace_of_clamps_unknown_to_default():
    """A stale/garbage value (not one of the 4 options) falls back to default."""
    assert pace_of({"new_pace": 999}) == DEFAULT_PACE
    assert pace_of({"new_pace": 8}) == DEFAULT_PACE  # 8 isn't an option
    assert pace_of({"new_pace": "nonsense"}) == DEFAULT_PACE
    assert pace_of({"new_pace": None}) == DEFAULT_PACE


def test_pace_of_accepts_numeric_string():
    assert pace_of({"new_pace": "25"}) == 25


def test_ceiling_is_three_times_pace():
    assert ceiling_of(3) == 9
    assert ceiling_of(7) == 21
    assert ceiling_of(15) == 45
    assert ceiling_of(25) == 75


def test_ceiling_never_zero():
    assert ceiling_of(0) == 3  # max(1,0)*3 — defends against a silly pace


def test_all_pace_values_have_labels():
    for v in PACE_VALUES:
        lbl = label_for(v)
        assert lbl and "{" not in lbl


def test_label_for_unknown_falls_back_to_number():
    assert label_for(99) == "99"


# ---- pool size derived from real throughput ----


def test_pool_tracks_how_much_the_user_actually_answers():
    assert pool_ceiling(4) < pool_ceiling(10) < pool_ceiling(20)


def test_the_shape_that_works_in_prod_is_preserved():
    """User 3 answers ~13.9/day with 22 active words and has mastered the most.
    That ratio is the calibration target."""
    assert 18 <= pool_ceiling(13.9) <= 24


def test_the_broken_prod_case_is_cut_down():
    """User 1 sat at 63 active words on 8.9 answers/day — a word every ~7 days."""
    assert pool_ceiling(8.9) < 20


def test_no_history_gets_a_modest_pool_not_a_huge_one():
    for empty in (None, 0, -1):
        assert MIN_POOL <= pool_ceiling(empty) <= 12


def test_pool_stays_inside_its_bounds():
    assert pool_ceiling(0.1) >= MIN_POOL
    assert pool_ceiling(1000) == MAX_POOL


def test_a_beginner_still_gets_something_to_learn():
    assert pool_ceiling(1) >= MIN_POOL


# ---- offering to drain an oversized pool ----


def test_a_pool_that_fits_is_left_alone():
    assert overflow(active=10, ceiling=16) == 0


def test_a_small_excess_is_not_worth_interrupting_for():
    assert overflow(active=15, ceiling=16) == 0


def test_the_prod_case_is_offered():
    """User 1 sat on 63 active words against a ceiling of 16 and could not
    receive a single new one until they drained it."""
    assert overflow(active=63, ceiling=16) > 0


def test_no_single_offer_takes_more_than_half():
    """Correct arithmetic wanted 48 of one user's 63 words in one tap. Every
    one comes back, and it is still a lot to hand over at once."""
    assert overflow(active=63, ceiling=16) <= 63 // 2
    assert overflow(active=20, ceiling=6) <= 20 // 2


def test_repeated_offers_converge_below_the_ceiling():
    """Capping each round means the pool needs a few, so what matters is that
    they end — a new word only enters while the pool is UNDER the ceiling."""
    ceiling, active, rounds = 16, 63, 0
    while (to_park := overflow(active, ceiling)) and rounds < 20:
        assert to_park > 0
        active -= to_park
        rounds += 1
    assert active < ceiling
    assert rounds <= 5  # a few visible steps, not a grind


def test_it_never_asks_to_park_below_the_floor():
    to_park = overflow(active=40, ceiling=MIN_POOL)
    assert 40 - to_park >= MIN_POOL


def test_the_floor_is_a_resting_place_not_a_trap():
    """A very light user's ceiling equals MIN_POOL, so draining can't take them
    below it. That's the designed floor, not a stall: at five words on two
    answers a day each one comes back every few days and graduates, and intake
    resumes as slots free up."""
    assert overflow(active=MIN_POOL, ceiling=MIN_POOL) == 0
