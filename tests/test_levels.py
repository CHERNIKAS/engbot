from __future__ import annotations

from app.domain.levels import (
    DEFAULT_LEVEL,
    LEVELS,
    DEMOTE_ACCURACY,
    DEMOTE_MIN_ATTEMPTS,
    MASTERY_REPS_MIN,
    PROMOTE_MASTERED,
    estimate_level,
    gap,
    index,
    ladder_stages,
    mastery_reps,
    normalize,
    recalibrated_level,
    selection_rank,
    shift,
    source_rank,
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


# ---- selection ranking (what gets taught next) ----


def test_at_level_words_are_picked_before_anything_else():
    ranks = {lvl: selection_rank(lvl, "B1") for lvl in ("A1", "A2", "B1", "B2", "C1")}
    assert ranks["B1"] == min(ranks.values())


def test_one_step_down_beats_one_step_up():
    """A winnable word keeps someone going; the stretch comes second."""
    assert selection_rank("A2", "B1") < selection_rank("B2", "B1")


def test_two_steps_away_is_worse_than_one_in_either_direction():
    for near in ("A2", "B2"):
        for far in ("A1", "C1"):
            assert selection_rank(near, "B1") < selection_rank(far, "B1")


def test_untagged_word_lands_between_one_down_and_one_up():
    assert selection_rank("A2", "B1") <= selection_rank(None, "B1") <= selection_rank("B2", "B1")


def test_user_additions_outrank_pack_filler():
    assert source_rank("manual") < source_rank("pack")
    assert source_rank("txt_import") < source_rank("pack")
    assert source_rank("course") < source_rank("pack")
    assert source_rank(None) == source_rank("pack")


# ---- mastery bar ----


def test_bar_grows_with_difficulty():
    assert mastery_reps("A1", "B1") < mastery_reps("B1", "B1") < mastery_reps("B2", "B1")


def test_bar_at_level_is_reachable_unlike_the_old_flat_ten():
    # Prod peaked at 9 reps and never crossed the flat bar of 10.
    assert mastery_reps("B1", "B1") < 10


def test_bar_never_drops_below_the_floor():
    assert mastery_reps("A1", "C2") >= MASTERY_REPS_MIN


def test_untagged_word_is_treated_as_at_level_not_as_hard():
    assert mastery_reps(None, "B1") == mastery_reps("B1", "B1")


# ---- ladder stages ----


def test_legacy_bar_keeps_its_original_rungs():
    assert ladder_stages(10) == (3, 5)


def test_rungs_stay_distinct_and_ordered_at_every_bar():
    for target in range(MASTERY_REPS_MIN, 13):
        reverse_at, cloze_at = ladder_stages(target)
        assert 1 <= reverse_at < cloze_at


def test_shortest_bar_still_leaves_room_to_produce_the_word():
    _reverse_at, cloze_at = ladder_stages(MASTERY_REPS_MIN)
    assert cloze_at < MASTERY_REPS_MIN


# ---- recalibration ----


def test_enough_mastered_at_or_above_promotes_one_step():
    assert recalibrated_level("A2", PROMOTE_MASTERED, 0, 0) == "B1"


def test_promotion_moves_only_one_step_however_strong_the_evidence():
    assert recalibrated_level("A1", PROMOTE_MASTERED * 10, 0, 0) == "A2"


def test_just_short_of_the_evidence_bar_changes_nothing():
    assert recalibrated_level("A2", PROMOTE_MASTERED - 1, 0, 0) is None


def test_sustained_failure_at_level_demotes():
    attempts = DEMOTE_MIN_ATTEMPTS
    correct = int(attempts * (DEMOTE_ACCURACY - 0.1))
    assert recalibrated_level("B1", 0, attempts, correct) == "A2"


def test_a_bad_evening_is_not_enough_to_demote():
    """Small samples must not move anyone — being wrong is how learning looks."""
    assert recalibrated_level("B1", 0, DEMOTE_MIN_ATTEMPTS - 1, 0) is None


def test_ordinary_accuracy_leaves_the_level_alone():
    attempts = DEMOTE_MIN_ATTEMPTS * 2
    assert recalibrated_level("B1", 0, attempts, int(attempts * 0.7)) is None


def test_promotion_wins_when_both_signals_fire():
    """Mastering a lot while also missing a lot means they're stretching, not drowning."""
    attempts = DEMOTE_MIN_ATTEMPTS
    assert recalibrated_level("A2", PROMOTE_MASTERED, attempts, 0) == "B1"


def test_no_move_past_the_ends_of_the_scale():
    assert recalibrated_level(LEVELS[-1], PROMOTE_MASTERED * 5, 0, 0) is None
    assert recalibrated_level(LEVELS[0], 0, DEMOTE_MIN_ATTEMPTS, 0) is None


def test_unplaced_user_is_recalibrated_from_the_default():
    assert recalibrated_level(None, PROMOTE_MASTERED, 0, 0) == shift(DEFAULT_LEVEL, 1)
