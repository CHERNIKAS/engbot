from __future__ import annotations

# Pure, I/O-free helpers for the guided course ("🎓 Курс"). The course is an
# ordered spine of words (A1→A2→B1→B2); the bot auto-feeds the next words into
# the user's vocabulary so the all-day push delivers them in order. These
# functions decide lesson numbering and which words to top up — the DB side lives
# in CourseService.

from app.domain.enums import WordStatus

LESSON_SIZE = 10

# A word the user dismissed with «я знаю» reports this sentinel from status_map
# (see UserWordRepository.status_map). It's "done" for pipeline purposes: it
# frees its buffer slot and counts toward course completion, but is never
# re-added (it's still owned).
ARCHIVED_STATUS = "archived"
_DONE = frozenset({WordStatus.MASTERED.value, ARCHIVED_STATUS})


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
    words actively in progress (owned, not yet mastered, not dismissed).

    - counts owned words that are neither mastered nor archived as "in progress";
    - tops up the deficit with the next not-yet-owned spine words, in order;
    - never re-adds owned words (archived included — they're owned, just parked),
      so a dismissed word frees its slot and the next word flows in;
    - returns [] when the pipeline is already full or the spine is exhausted.
    """
    if goal <= 0:
        return []
    in_progress = sum(1 for w in spine if w in owned and owned[w] not in _DONE)
    need = goal - in_progress
    if need <= 0:
        return []
    not_owned = [w for w in spine if w not in owned]
    return not_owned[:need]
