from __future__ import annotations

from app.domain.levels import (
    DEFAULT_LEVEL,
    LEVELS,
    estimate_level,
    gap,
    index,
    normalize,
    shift,
)


def test_levels_are_ordered_easiest_first():
    assert LEVELS[0] == "A1"
    assert index("A1") < index("A2") < index("B1") < index("B2") < index("C1")


def test_unknown_level_reads_as_default():
    assert index(None) == index(DEFAULT_LEVEL)
    assert index("Z9") == index(DEFAULT_LEVEL)
    assert normalize(None) == DEFAULT_LEVEL
    assert normalize("") == DEFAULT_LEVEL
    assert normalize("nonsense") == DEFAULT_LEVEL


def test_normalize_accepts_sloppy_casing():
    assert normalize("b1") == "B1"
    assert normalize(" a2 ") == "A2"


def test_gap_signs_which_side_the_word_is_on():
    assert gap("A1", "B1") == -2  # word below the user
    assert gap("B1", "B1") == 0  # right at their level
    assert gap("B2", "B1") == 1  # one step of stretch


def test_shift_clamps_at_both_ends():
    assert shift("A1", -5) == "A1"
    assert shift("C2", 5) == "C2"
    assert shift("A2", 1) == "B1"


def test_estimate_takes_hardest_level_still_held():
    answers = {
        "A1": [True, True, True],
        "A2": [True, True, False],  # 2/3 — still held
        "B1": [False, False, True],  # 1/3 — fails here
        "B2": [False, False, False],
    }
    assert estimate_level(answers) == "A2"


def test_estimate_stops_at_first_failure_despite_a_lucky_guess_above():
    # Failing B1 but passing B2 is luck, not ability — the walk must stop at B1.
    answers = {
        "A1": [True, True, True],
        "A2": [True, True, True],
        "B1": [False, True, False],
        "B2": [True, True, True],
    }
    assert estimate_level(answers) == "A2"


def test_estimate_floors_at_a1_when_nothing_is_held():
    answers = {"A1": [False, False, False], "A2": [False, False, False]}
    assert estimate_level(answers) == "A1"


def test_estimate_caps_at_the_hardest_tested_level():
    answers = {lvl: [True, True, True] for lvl in ("A1", "A2", "B1", "B2")}
    assert estimate_level(answers) == "B2"


def test_estimate_handles_a_missing_or_empty_level_block():
    assert estimate_level({}) == "A1"
    assert estimate_level({"A1": [True, True, True], "A2": []}) == "A1"
