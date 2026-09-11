from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain import mastery
from app.domain.enums import LearningPace, ReviewResult, WordStatus
from app.services.repetition_service import (
    MASTERED_REPS_EASY,
    MASTERED_REPS_NORMAL,
    MAX_INTERVAL_DAYS,
    MASTERY_SCORE_MAX,
    apply_review,
)


def _make_uw(**overrides) -> SimpleNamespace:
    base = dict(
        ease_score=2.5,
        repetitions_count=0,
        mistakes_count=0,
        interval_days=0.0,
        last_reviewed_at=None,
        next_review_at=datetime.now(timezone.utc),
        status=WordStatus.NEW.value,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_normal_grows_interval_and_advances_status():
    uw = _make_uw()
    now = datetime(2025, 1, 1)
    apply_review(uw, ReviewResult.NORMAL, LearningPace.NORMAL, now=now)
    assert uw.status == WordStatus.LEARNING.value
    assert uw.repetitions_count == 1
    assert uw.interval_days >= 1.0


def test_easy_boosts_ease_and_can_master_after_repeated_use():
    uw = _make_uw(repetitions_count=3, ease_score=2.6, status=WordStatus.REVIEW.value, interval_days=10)
    apply_review(uw, ReviewResult.EASY, LearningPace.NORMAL)
    assert uw.status == WordStatus.MASTERED.value
    assert uw.ease_score >= 2.6


def test_hard_shrinks_interval_and_increments_mistakes():
    uw = _make_uw(repetitions_count=3, interval_days=8.0, ease_score=2.4, status=WordStatus.REVIEW.value)
    apply_review(uw, ReviewResult.HARD, LearningPace.NORMAL)
    assert uw.status == WordStatus.LEARNING.value
    assert uw.mistakes_count == 1
    assert uw.interval_days < 8.0


def test_wrong_drops_a_couple_steps_not_to_zero():
    """A miss drops the streak by LAPSE_DROP (2), not all the way to 0 — so the
    production ladder doesn't make 10-in-a-row unreachable (prod regression)."""
    uw = _make_uw(repetitions_count=8, interval_days=20.0, status=WordStatus.REVIEW.value)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL)
    assert uw.repetitions_count == 6  # 8 - 2
    assert uw.mistakes_count == 1
    assert uw.interval_days < 1.0
    assert uw.status == WordStatus.LEARNING.value


def test_wrong_floors_at_zero():
    uw = _make_uw(repetitions_count=1, status=WordStatus.LEARNING.value)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL)
    assert uw.repetitions_count == 0  # max(0, 1-2)


def test_mastery_reachable_with_occasional_misses():
    """Sim: ~83% accuracy (5 correct, 1 wrong, repeating) must eventually reach
    MASTERED — the whole point of softening the reset."""
    uw = _make_uw()
    pattern = [True, True, True, True, True, False]  # 5 right, 1 wrong
    for i in range(120):
        if uw.status == WordStatus.MASTERED.value:
            break
        ok = pattern[i % len(pattern)]
        apply_review(uw, ReviewResult.CORRECT if ok else ReviewResult.WRONG, LearningPace.NORMAL)
    assert uw.status == WordStatus.MASTERED.value


def test_mastered_zero_score_not_teleported_up():
    """A mastered word at score 0.0 (forgotten to the floor) must stay near the
    floor on a wrong answer, not jump back to ~5.0 (the `or` bug)."""
    uw = _make_uw(status=WordStatus.MASTERED.value, mastery_score=0.0)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL)
    assert uw.mastery_score == 0.0  # max(0, 0.0 - 0.1)


def test_mastered_zero_score_correct_climbs_from_floor():
    uw = _make_uw(status=WordStatus.MASTERED.value, mastery_score=0.0)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL)
    assert uw.mastery_score == 0.1  # not 5.0 + 0.1


def test_mastered_none_score_defaults_to_max():
    uw = _make_uw(status=WordStatus.MASTERED.value, mastery_score=None)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL)
    assert uw.mastery_score == MASTERY_SCORE_MAX  # None = "no score yet" → 5.0


def test_pace_modifies_final_interval():
    uw_normal = _make_uw(interval_days=4.0, repetitions_count=2, status=WordStatus.REVIEW.value)
    apply_review(uw_normal, ReviewResult.NORMAL, LearningPace.NORMAL)
    uw_chill = _make_uw(interval_days=4.0, repetitions_count=2, status=WordStatus.REVIEW.value)
    apply_review(uw_chill, ReviewResult.NORMAL, LearningPace.CHILL)
    assert uw_chill.interval_days > uw_normal.interval_days


def test_next_review_at_uses_now():
    uw = _make_uw()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    apply_review(uw, ReviewResult.NORMAL, LearningPace.NORMAL, now=now)
    assert uw.last_reviewed_at == now
    assert uw.next_review_at >= now + timedelta(days=uw.interval_days * 0.9)


# ---- weighted score + production floor ----


def _uw_fresh() -> SimpleNamespace:
    return _make_uw(learning_score=0.0, production_count=0, mastery_score=0.0)


def test_choice_cards_alone_never_graduate_a_word():
    """The regression that mattered: 8% of four-option answers are guesses, and
    the old rule let a word graduate on nothing else."""
    uw = _uw_fresh()
    for _ in range(40):
        apply_review(
            uw, ReviewResult.CORRECT, LearningPace.NORMAL,
            kind=mastery.RECOGNITION, word_level="B1", user_level="B1",
        )
    assert uw.status != WordStatus.MASTERED.value
    assert uw.production_count == 0


def test_typed_answers_graduate_a_word():
    uw = _uw_fresh()
    for _ in range(12):
        apply_review(
            uw, ReviewResult.CORRECT, LearningPace.NORMAL,
            kind=mastery.TYPED_EXACT, word_level="B1", user_level="B1",
        )
        if uw.status == WordStatus.MASTERED.value:
            break
    assert uw.status == WordStatus.MASTERED.value
    assert uw.production_count >= 3


def test_a_miss_costs_score():
    uw = _uw_fresh()
    apply_review(
        uw, ReviewResult.CORRECT, LearningPace.NORMAL,
        kind=mastery.TYPED_EXACT, word_level="B1", user_level="B1",
    )
    before = uw.learning_score
    apply_review(
        uw, ReviewResult.WRONG, LearningPace.NORMAL,
        kind=mastery.WRONG, word_level="B1", user_level="B1",
    )
    assert uw.learning_score < before


def test_grammar_items_keep_the_legacy_rule():
    """No CEFR level and no typed stage — the score has nothing to weigh."""
    uw = _uw_fresh()
    for _ in range(MASTERED_REPS_NORMAL):
        apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL)
    assert uw.status == WordStatus.MASTERED.value


def test_interval_is_capped_so_it_cannot_overflow_a_date():
    """A word answered forever without graduating used to compound its interval
    until `now + timedelta(days=...)` raised OverflowError mid-answer."""
    uw = _uw_fresh()
    for _ in range(200):
        apply_review(
            uw, ReviewResult.CORRECT, LearningPace.NORMAL,
            kind=mastery.RECOGNITION, word_level="B1", user_level="B1",
        )
    assert uw.interval_days <= MAX_INTERVAL_DAYS


def test_the_easy_shortcut_still_needs_typed_answers():
    """EASY skips reps, not the gates. Mastering here on choice cards alone
    would reopen the hole the production floor exists to close."""
    uw = _uw_fresh()
    for _ in range(20):
        apply_review(
            uw, ReviewResult.EASY, LearningPace.NORMAL,
            kind=mastery.RECOGNITION, word_level="B1", user_level="B1",
        )
    assert uw.status != WordStatus.MASTERED.value
    assert uw.production_count == 0


def test_the_easy_shortcut_keeps_the_legacy_rule_without_a_kind():
    """Grammar items come through here with no answer kind and no CEFR level."""
    uw = _uw_fresh()
    for _ in range(MASTERED_REPS_EASY + 1):
        apply_review(uw, ReviewResult.EASY, LearningPace.NORMAL)
    assert uw.status == WordStatus.MASTERED.value


# ---- a mastered word is rescheduled by its review, like any other ----


def _mastered(**overrides) -> SimpleNamespace:
    base = dict(status=WordStatus.MASTERED.value, mastery_score=5.0, interval_days=10.0)
    base.update(overrides)
    return _make_uw(**base)


def test_a_correct_review_pushes_a_mastered_word_into_the_future():
    """Prod: `never` answered four times in five days, next_review_at still on
    17 July. A review that doesn't reschedule leaves the word due forever."""
    now = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    uw = _mastered(next_review_at=datetime(2026, 7, 17, tzinfo=timezone.utc))
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL, now=now)
    assert uw.next_review_at > now + timedelta(days=1)
    assert uw.last_reviewed_at == now


def test_each_correct_review_spaces_a_mastered_word_further():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    uw = _mastered()
    gaps = []
    for _ in range(3):
        apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL, now=now)
        gaps.append(uw.interval_days)
    assert gaps[0] > 10.0
    assert gaps[0] < gaps[1] < gaps[2]


def test_a_mastered_interval_never_passes_the_cap():
    uw = _mastered(interval_days=MAX_INTERVAL_DAYS)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL)
    assert uw.interval_days <= MAX_INTERVAL_DAYS


def test_a_miss_on_a_mastered_word_brings_it_back_tomorrow():
    """Still learned — but a slip means checking soon, not in a month."""
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    uw = _mastered(interval_days=40.0)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL, now=now)
    assert uw.status == WordStatus.MASTERED.value
    assert timedelta(hours=20) <= uw.next_review_at - now <= timedelta(days=2)
    assert uw.ease_score < 2.5
    assert uw.mastery_score == 4.9


def test_a_mastered_word_with_no_interval_yet_still_gets_one():
    """Words that graduated through old code paths can carry 0.0."""
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    uw = _mastered(interval_days=0.0)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL, now=now)
    assert uw.interval_days >= 1.0
    assert uw.next_review_at >= now + timedelta(days=1)


# ---- holes found by mutation testing ----


def test_a_miss_makes_the_word_harder_not_easier():
    """`ease - 0.25` → `ease + 0.25` survived: a wrong answer that makes the
    word grow faster from then on."""
    for result in (ReviewResult.WRONG, ReviewResult.HARD):
        uw = _make_uw(status=WordStatus.REVIEW.value, ease_score=2.5, interval_days=5.0)
        apply_review(uw, result, LearningPace.NORMAL)
        assert uw.ease_score < 2.5, result


def test_a_correct_answer_spaces_the_word_further_than_last_time():
    """`interval * ease` → `interval / ease` survived: every existing check
    started from interval 0, where both land on the one-day floor."""
    uw = _make_uw(status=WordStatus.REVIEW.value, interval_days=4.0, repetitions_count=3)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL)
    assert uw.interval_days > 4.0


def test_a_typed_answer_counts_exactly_once_toward_the_floor():
    """Counting +2 per typed answer would halve the production floor."""
    uw = _make_uw(status=WordStatus.REVIEW.value, learning_score=1.0, production_count=1)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL, kind=mastery.TYPED_EXACT)
    assert uw.production_count == 2


def test_a_choice_answer_does_not_count_as_typing():
    uw = _make_uw(status=WordStatus.REVIEW.value, learning_score=1.0, production_count=1)
    apply_review(uw, ReviewResult.CORRECT, LearningPace.NORMAL, kind=mastery.RECOGNITION)
    assert uw.production_count == 1


def test_a_lapse_brings_an_active_word_back_the_same_day():
    now = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
    uw = _make_uw(status=WordStatus.REVIEW.value, interval_days=12.0)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL, now=now)
    assert uw.next_review_at - now < timedelta(hours=12)


def test_a_mastered_lapse_returns_within_a_day():
    """The looser check above allowed two days, so `interval = 2.0` survived."""
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    uw = _mastered(interval_days=40.0)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL, now=now)
    assert uw.next_review_at - now <= timedelta(days=1)


def test_a_mastered_miss_is_counted_as_a_mistake():
    uw = _mastered(mistakes_count=2)
    apply_review(uw, ReviewResult.WRONG, LearningPace.NORMAL)
    assert uw.mistakes_count == 3


def test_the_learned_ceiling_is_five():
    """The card says «Выучено на X из 5» — the ceiling is copy, not a knob.
    Every other check compared against the constant itself."""
    assert MASTERY_SCORE_MAX == 5.0
