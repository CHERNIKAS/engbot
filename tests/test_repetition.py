from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.enums import LearningPace, ReviewResult, WordStatus
from app.services.repetition_service import apply_review


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
