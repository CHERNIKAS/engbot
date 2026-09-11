from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.enums import (
    PACE_INTERVAL_MULTIPLIER,
    LearningPace,
    ReviewResult,
    WordStatus,
)
from app.domain.mastery import apply_credit, is_mastered, is_production
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
# Hard cap on a review interval. Each correct answer multiplies the interval by
# ease, and nothing else bounds it: a word that keeps being answered but never
# graduates compounds forever, and `now + timedelta(days=interval)` eventually
# raises OverflowError and takes the answer handler down with it. That became
# reachable once mastery started requiring typed answers — a word answered only
# on choice cards is exactly such a word. A year is far past the point where
# the interval means anything anyway.
MAX_INTERVAL_DAYS = 365.0
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
    kind: str | None = None,
    word_level: str | None = None,
    user_level: str | None = None,
    production_possible: bool = True,
) -> UserWord:
    """Mutates user_word in place with new ease/interval/status based on result+pace.

    Pass `kind` (an app.domain.mastery answer kind) to grade on the weighted
    score: credit reflects what the answer proved, and mastery additionally
    needs a floor of typed answers, so a word can't graduate on guessable cards.

    Without `kind` the legacy rep-count rule applies, with `mastered_reps` as the
    bar. Grammar items take that path — they have no CEFR level and no typed
    stage, so there is nothing for the score to weigh.
    """
    now = now or datetime.now(timezone.utc)
    target_reps = MASTERED_REPS_NORMAL if mastered_reps is None else max(1, mastered_reps)

    # Mastered words never leave the "learned" pool (no return to active study):
    # their 0–5 score moves +step on correct, -step on wrong — and, like any
    # other word, a review reschedules them.
    #
    # It used to stop at the score. interval_days and next_review_at were left
    # exactly where graduation put them, so once a mastered word came due it
    # stayed due forever: prod had `never` answered four times in five days with
    # next_review_at still sitting on 17 July. Nothing noticed because the
    # picker ignored the due date too — fixing only that would have made such a
    # word the single "due" one and served it on every review draw.
    if user_word.status == WordStatus.MASTERED.value:
        # `or` would treat a legitimate 0.0 (a mastered word forgotten down to
        # the floor) as "unset" and teleport it back to ~5.0 on the next
        # review. Only a true None means "no score yet".
        score = user_word.mastery_score if user_word.mastery_score is not None else MASTERY_SCORE_MAX
        ease = user_word.ease_score or 2.5
        if result in (ReviewResult.CORRECT, ReviewResult.NORMAL, ReviewResult.EASY):
            score = min(MASTERY_SCORE_MAX, score + MASTERY_SCORE_STEP)
            interval = max(user_word.interval_days or 0.0, 1.0) * ease
        else:  # WRONG / HARD
            score = max(0.0, score - MASTERY_SCORE_STEP)
            user_word.mistakes_count += 1
            # A lapse on a learned word: back tomorrow to check it isn't really
            # gone, and grow more cautiously from there. Standard SRS relearn —
            # halving a two-month interval would leave a forgotten word unseen
            # for another month.
            ease = _clamp(ease - 0.2, MIN_EASE, MAX_EASE)
            interval = 1.0
        final_interval = _clamp(
            interval * PACE_INTERVAL_MULTIPLIER.get(pace, 1.0), 1.0, MAX_INTERVAL_DAYS
        )
        user_word.mastery_score = round(score, 2)
        user_word.ease_score = ease
        user_word.interval_days = final_interval
        user_word.last_reviewed_at = now
        user_word.next_review_at = now + timedelta(days=final_interval)
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
        if kind is not None:
            user_word.learning_score = apply_credit(user_word.learning_score or 0.0, kind)
            if is_production(kind):
                user_word.production_count = (user_word.production_count or 0) + 1
        # The shortcut is only a shortcut on the rep count. It must still clear
        # the same gates as the normal path: reaching "learned" here without a
        # typed answer would reopen the exact hole the production floor closes,
        # and this branch is unreachable today only because nothing emits EASY.
        graduated = (
            is_mastered(
                user_word.learning_score,
                user_word.production_count,
                word_level,
                user_level,
                production_possible=production_possible,
            )
            if kind is not None
            else (reps >= MASTERED_REPS_EASY and ease >= 2.6)
        )
        if graduated:
            user_word.status = WordStatus.MASTERED.value
            user_word.mastery_score = MASTERY_SCORE_MAX
        else:
            user_word.status = WordStatus.REVIEW.value
    elif result in (ReviewResult.NORMAL, ReviewResult.CORRECT):
        interval = max(interval * ease, 1.0) if interval > 0 else 1.0
        reps += 1
        if kind is not None:
            user_word.learning_score = apply_credit(user_word.learning_score or 0.0, kind)
            if is_production(kind):
                user_word.production_count = (user_word.production_count or 0) + 1
            graduated = is_mastered(
                user_word.learning_score,
                user_word.production_count,
                word_level,
                user_level,
                production_possible=production_possible,
            )
        else:
            graduated = reps >= target_reps
        if graduated:
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
        if kind is not None:
            user_word.learning_score = apply_credit(user_word.learning_score or 0.0, kind)
        ease = _clamp(ease - 0.25, MIN_EASE, MAX_EASE)
        interval = 0.25  # ~6 hours
        reps = max(0, reps - LAPSE_DROP)  # drop one rung, don't wipe all progress
        mistakes += 1
        user_word.status = WordStatus.LEARNING.value

    final_interval = min(interval * pace_mult, MAX_INTERVAL_DAYS)
    user_word.ease_score = ease
    user_word.interval_days = final_interval
    user_word.repetitions_count = reps
    user_word.mistakes_count = mistakes
    user_word.last_reviewed_at = now
    user_word.next_review_at = now + timedelta(days=final_interval)
    return user_word
