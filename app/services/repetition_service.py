from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.enums import (
    PACE_INTERVAL_MULTIPLIER,
    LearningPace,
    ReviewResult,
    WordStatus,
)
from app.domain.models import UserWord


MIN_EASE = 1.3
MAX_EASE = 3.0
MASTERED_REPS_EASY = 4
MASTERED_REPS_NORMAL = 6


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def apply_review(
    user_word: UserWord,
    result: ReviewResult,
    pace: LearningPace,
    now: datetime | None = None,
) -> UserWord:
    """Mutates user_word in place with new ease/interval/status based on result+pace."""
    now = now or datetime.now(timezone.utc)
    pace_mult = PACE_INTERVAL_MULTIPLIER.get(pace, 1.0)
    ease = user_word.ease_score or 2.5
    interval = max(user_word.interval_days, 0.0)
    reps = user_word.repetitions_count
    mistakes = user_word.mistakes_count

    if result in (ReviewResult.EASY,):
        ease = _clamp(ease + 0.15, MIN_EASE, MAX_EASE)
        interval = max(interval * ease, 4.0) if interval > 0 else 4.0
        reps += 1
        if reps >= MASTERED_REPS_EASY and ease >= 2.6:
            user_word.status = WordStatus.MASTERED.value
        else:
            user_word.status = WordStatus.REVIEW.value
    elif result in (ReviewResult.NORMAL, ReviewResult.CORRECT):
        interval = max(interval * ease, 1.0) if interval > 0 else 1.0
        reps += 1
        if reps >= MASTERED_REPS_NORMAL:
            user_word.status = WordStatus.MASTERED.value
        elif user_word.status == WordStatus.NEW.value:
            user_word.status = WordStatus.LEARNING.value
        else:
            user_word.status = WordStatus.REVIEW.value
    elif result == ReviewResult.HARD:
        ease = _clamp(ease - 0.2, MIN_EASE, MAX_EASE)
        interval = max(interval * 0.5, 0.5) if interval > 0 else 0.5
        mistakes += 1
        user_word.status = WordStatus.LEARNING.value
    elif result == ReviewResult.WRONG:
        ease = _clamp(ease - 0.25, MIN_EASE, MAX_EASE)
        interval = 0.25  # ~6 hours
        reps = 0
        mistakes += 1
        user_word.status = WordStatus.LEARNING.value

    final_interval = interval * pace_mult
    user_word.ease_score = ease
    user_word.interval_days = final_interval
    user_word.repetitions_count = reps
    user_word.mistakes_count = mistakes
    user_word.last_reviewed_at = now
    user_word.next_review_at = now + timedelta(days=final_interval)
    return user_word
