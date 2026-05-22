from __future__ import annotations

# Pure, I/O-free helpers for the guided course ("🎓 Курс"). The course is an
# ordered spine of words (A1→A2→B1→B2); the bot auto-feeds the next words into
# the user's vocabulary so the all-day push delivers them in order. These
# functions decide lesson numbering and which words to top up — the DB side lives
# in CourseService.

from app.domain.enums import WordStatus

LESSON_SIZE = 10


def total_lessons(spine_len: int, size: int = LESSON_SIZE) -> int:
    if spine_len <= 0:
        return 0
    return (spine_len + size - 1) // size


def current_lesson(mastered_count: int, spine_len: int, size: int = LESSON_SIZE) -> int:
    """1-based lesson the learner is currently on (the first not-yet-mastered
    chunk). Clamped to the last lesson once everything is mastered."""
    total = total_lessons(spine_len, size)
    if total == 0:
        return 0
    return min(total, mastered_count // size + 1)


def words_to_add(spine: list[int], owned: dict[int, str], goal: int) -> list[int]:
    """Which spine words to pull into the user's vocab so they have up to `goal`
    words actively in progress (owned but not yet mastered).

    - counts owned, non-mastered spine words as "in progress";
    - tops up the deficit with the next not-yet-owned spine words, in order;
    - never re-adds owned words; returns [] when the pipeline is already full or
      the spine is exhausted.
    """
    if goal <= 0:
        return []
    mastered = WordStatus.MASTERED.value
    in_progress = sum(1 for w in spine if w in owned and owned[w] != mastered)
    need = goal - in_progress
    if need <= 0:
        return []
    not_owned = [w for w in spine if w not in owned]
    return not_owned[:need]
