"""A hard answer brings the word back sooner, never later.

Study mode reports ReviewResult.HARD (study_session_service), so this branch
is live. Mutation testing had already pinned that HARD lowers ease, but the
interval itself was free: halving it could become multiplying by 1.25, and
a word the learner struggled with would drift further away.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.domain.enums import LearningPace, ReviewResult, WordStatus
from app.services.repetition_service import apply_review

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def _uw(interval: float):
    return SimpleNamespace(
        status=WordStatus.REVIEW.value, ease_score=2.5, repetitions_count=4,
        mistakes_count=0, interval_days=interval, last_reviewed_at=None, next_review_at=NOW,
    )


def test_a_hard_answer_shortens_the_interval():
    uw = _uw(8.0)
    apply_review(uw, ReviewResult.HARD, LearningPace.NORMAL, now=NOW)
    assert uw.interval_days < 8.0


def test_a_hard_answer_on_a_new_interval_still_schedules_it():
    uw = _uw(0.0)
    apply_review(uw, ReviewResult.HARD, LearningPace.NORMAL, now=NOW)
    assert 0 < uw.interval_days < 1.0
