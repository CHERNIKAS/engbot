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
MASTERED_REPS_NORMAL = 10  # push v2: 10 correct in a row to learn a word
MASTERY_SCORE_MAX = 5.0
MASTERY_SCORE_STEP = 0.1  # mastered word: +0.1 correct / -0.1 wrong


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

    # Mastered words never leave the "learned" pool (no return to active study);
    # only their 0–5 score moves: +step on correct, -step on wrong.
    if user_word.status == WordStatus.MASTERED.value:
        score = user_word.mastery_score or MASTERY_SCORE_MAX
        if result in (ReviewResult.CORRECT, ReviewResult.NORMAL, ReviewResult.EASY):
            score = min(MASTERY_SCORE_MAX, score + MASTERY_SCORE_STEP)
        else:  # WRONG / HARD
            score = max(0.0, score - MASTERY_SCORE_STEP)
            user_word.mistakes_count += 1
        user_word.mastery_score = round(score, 2)
        user_word.last_reviewed_at = now
        return user_word

    pace_mult = PACE_INTERVAL_MULTIPLIER.get(pace, 1.0)
    ease = user_word.ease_score or 2.5
    interval = max(user_word.interval_days or 0.0, 0.0)
    reps = user_word.repetitions_count or 0
    mistakes = user_word.mistakes_count or 0

    if result in (ReviewResult.EASY,):
        ease = _clamp(ease + 0.15, MIN_EASE, MAX_EASE)
        interval = max(interval * ease, 4.0) if interval > 0 else 4.0
        reps += 1
        if reps >= MASTERED_REPS_EASY and ease >= 2.6:
            user_word.status = WordStatus.MASTERED.value
            user_word.mastery_score = MASTERY_SCORE_MAX
        else:
            user_word.status = WordStatus.REVIEW.value
    elif result in (ReviewResult.NORMAL, ReviewResult.CORRECT):
        interval = max(interval * ease, 1.0) if interval > 0 else 1.0
        reps += 1
        if reps >= MASTERED_REPS_NORMAL:
            user_word.status = WordStatus.MASTERED.value
            user_word.mastery_score = MASTERY_SCORE_MAX
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
