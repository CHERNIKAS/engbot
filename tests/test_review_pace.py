"""The pace setting stretches or shrinks every review interval.

Every scheduler test ran LearningPace.NORMAL, where the multiplier is 1.0 —
so `interval * pace` and `interval / pace` were indistinguishable and mutation
testing found the direction completely unpinned. A flipped multiplier would
make «💀 Hardcore» the slowest setting and «Спокойно» the most relentless.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.domain.enums import LearningPace, ReviewResult, WordStatus
from app.services.repetition_service import apply_review

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
SLOW_TO_FAST = [
    LearningPace.CHILL,
    LearningPace.NORMAL,
    LearningPace.INTENSIVE,
    LearningPace.HARDCORE,
]


def _next_interval(status: str, interval: float, pace: LearningPace) -> float:
    uw = SimpleNamespace(
        status=status,
        ease_score=2.5,
        repetitions_count=3,
        mistakes_count=0,
        interval_days=interval,
        mastery_score=5.0,
        last_reviewed_at=None,
        next_review_at=NOW,
    )
    apply_review(uw, ReviewResult.CORRECT, pace, now=NOW)
    return uw.interval_days


def _strictly_shrinking(values: list[float]) -> bool:
    return all(a > b for a, b in zip(values, values[1:]))


def test_a_faster_pace_brings_an_active_word_back_sooner():
    gaps = [_next_interval(WordStatus.REVIEW.value, 4.0, p) for p in SLOW_TO_FAST]
    assert _strictly_shrinking(gaps), gaps


def test_a_faster_pace_brings_a_learned_word_back_sooner():
    gaps = [_next_interval(WordStatus.MASTERED.value, 20.0, p) for p in SLOW_TO_FAST]
    assert _strictly_shrinking(gaps), gaps


def test_hardcore_takes_six_tenths_of_a_normal_gap():
    normal = _next_interval(WordStatus.REVIEW.value, 4.0, LearningPace.NORMAL)
    hardcore = _next_interval(WordStatus.REVIEW.value, 4.0, LearningPace.HARDCORE)
    assert abs(hardcore - normal * 0.6) < 1e-9
