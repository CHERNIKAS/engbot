"""CEFR levels as a comparable scale, plus the placement-test scoring.

Pure and I/O-free on purpose: the picker, the mastery thresholds and the
onboarding test all need to reason about "how far is this word from this user",
and that reasoning has to be unit-testable without a database.
"""

from __future__ import annotations

# Ordered easiest -> hardest. Index in this list *is* the level's numeric value,
# so a gap is a plain subtraction.
LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

# The level a user gets when we have nothing to go on: the catalogue's own
# centre of mass sits at A1/A2, and starting someone too high is worse than
# starting them too low — an easy word costs one tap, a wall costs a user.
DEFAULT_LEVEL = "A2"

# Placement test: how many words of each level to show, easiest first.
TEST_LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2")
TEST_PER_LEVEL = 3
# Share of a level's words the user must recognise for that level to count as
# "held". 2 of 3 — one miss inside a level is noise, two is a signal.
TEST_PASS_RATIO = 2 / 3


def index(level: str | None) -> int:
    """Numeric position of a level; unknown/None reads as the default."""
    if level in LEVELS:
        return LEVELS.index(level)  # type: ignore[arg-type]
    return LEVELS.index(DEFAULT_LEVEL)


def normalize(level: str | None) -> str:
    """A stored level cleaned up for use — unknown values collapse to default."""
    if not level:
        return DEFAULT_LEVEL
    upper = level.strip().upper()
    return upper if upper in LEVELS else DEFAULT_LEVEL


def gap(word_level: str | None, user_level: str | None) -> int:
    """How much harder a word is than the user: negative = below their level,
    0 = at it, positive = above. Used by both the picker and the mastery bar."""
    return index(word_level) - index(user_level)


def shift(level: str | None, steps: int) -> str:
    """Move `steps` along the scale, clamped at both ends."""
    pos = index(level) + steps
    return LEVELS[max(0, min(len(LEVELS) - 1, pos))]


def estimate_level(answers: dict[str, list[bool]]) -> str:
    """Placement-test verdict.

    `answers` maps a CEFR level to the per-word "did you know it?" flags shown
    for that level. The result is the hardest level the user still holds, where
    "holds" means recognising at least TEST_PASS_RATIO of its words.

    Deliberately walks upward and stops at the first level the user fails,
    rather than taking the hardest passed level anywhere in the test: someone
    who guesses one B2 word right after failing B1 is a B1 learner who got
    lucky, not a B2 one.
    """
    held = LEVELS[0]
    for level in TEST_LEVELS:
        flags = answers.get(level) or []
        if not flags:
            break
        if sum(flags) / len(flags) < TEST_PASS_RATIO:
            break
        held = level
    return held
