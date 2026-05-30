from __future__ import annotations

from app.domain.pacing import (
    DEFAULT_PACE,
    PACE_VALUES,
    ceiling_of,
    label_for,
    pace_of,
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
