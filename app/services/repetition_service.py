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
MASTERED_REPS_NORMAL = 10  # correct answers (net) to learn a word — see LAPSE_DROP
# A wrong answer drops the streak by a couple of steps instead of wiping it to
# zero. Why: the push "production ladder" makes cards harder as reps climb
# (recognition→reverse choice at 0/3, cloze typing at 5), so a harsh drop made
# the mastery bar unreachable in practice — prod showed engaged users capping
# below the bar with 0 words ever mastered. -2 keeps a positive drift toward
# mastery for words answered ≳70% correctly, while still penalising; with the
# due-first picker a lapsed word returns within hours, so the loss is quickly
# recoverable.
LAPSE_DROP = 2
MASTERY_SCORE_MAX = 5.0
MASTERY_SCORE_STEP = 0.1  # mastered word: +0.1 correct / -0.1 wrong


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def apply_review(
    user_word: UserWord,
    result: ReviewResult,
    pace: LearningPace,
    now: datetime | None = None,
    mastered_reps: int | None = None,
) -> UserWord:
    """Mutates user_word in place with new ease/interval/status based on result+pace.

    `mastered_reps` is the bar for this particular word — callers that know the
    word's level and the user's pass `levels.mastery_reps(...)`, so an easy word
    stops being drilled sooner than a hard one. Defaults to the flat legacy bar
    for callers that don't (grammar items, which have no CEFR level).
    """
    now = now or datetime.now(timezone.utc)
    target_reps = MASTERED_REPS_NORMAL if mastered_reps is None else max(1, mastered_reps)

    # Mastered words never leave the "learned" pool (no return to active study);
    # only their 0–5 score moves: +step on correct, -step on wrong.
    if user_word.status == WordStatus.MASTERED.value:
        # `or` would treat a legitimate 0.0 (a mastered word forgotten down to
        # the floor — and pick_review_mastered shows those MOST) as "unset" and
        # teleport it back to ~5.0 on the next review. Only a true None means
        # "no score yet".
        score = user_word.mastery_score if user_word.mastery_score is not None else MASTERY_SCORE_MAX
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
        if reps >= target_reps:
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
        reps = max(0, reps - LAPSE_DROP)  # drop one rung, don't wipe all progress
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
