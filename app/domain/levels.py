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


# How a word's distance from the user orders the "what next?" queue. Lower
# sorts first. At-level words dominate; one step down comes next (a win the
# user can actually get keeps them going); one step up is the stretch that
# moves them. Two steps either way is a last resort — trivia or a wall.
_SELECTION_RANKS: dict[int, int] = {0: 0, -1: 1, 1: 2, -2: 4, 2: 5}
# An untagged word sits between "one down" and "one up": it's usually something
# the user typed in themselves, so it deserves a good slot, but its difficulty
# is unknown and shouldn't outrank a word we've actually measured.
UNKNOWN_LEVEL_RANK = 2
_FAR_RANK = 6


def selection_rank(word_level: str | None, user_level: str | None) -> int:
    """Queue priority for one candidate word — lower is picked sooner."""
    if not word_level:
        return UNKNOWN_LEVEL_RANK
    return _SELECTION_RANKS.get(gap(word_level, user_level), _FAR_RANK)


# Words the user chose themselves are worth more than catalogue filler, but only
# as a tiebreak inside the same difficulty band — letting a bulk TXT import jump
# the queue wholesale is how the old date-ordered picker went wrong.
SOURCE_PRIORITY: dict[str, int] = {"manual": 0, "txt_import": 0, "course": 1, "pack": 2}
DEFAULT_SOURCE_PRIORITY = 2


def source_rank(source: str | None) -> int:
    return SOURCE_PRIORITY.get(source or "", DEFAULT_SOURCE_PRIORITY)


# Correct answers needed to call a word learned, by how far above the user it
# sits. A flat bar of 10 was the old rule, and prod showed it never fired once:
# active words averaged 5.1 reps and peaked at 9, so the only words ever marked
# learned came in through the easy path or the "I know this" button. A word well
# below the user's level doesn't need ten passes to prove anything, and a word
# above them earns the long haul.
_MASTERY_REPS: dict[int, int] = {-2: 3, -1: 4, 0: 6, 1: 8}
MASTERY_REPS_FAR = 10
MASTERY_REPS_MIN = 3


def mastery_reps(word_level: str | None, user_level: str | None) -> int:
    """How many correct answers this word needs from this user to count as
    learned. Unknown word level is treated as at-level, not as hard."""
    if not word_level:
        return _MASTERY_REPS[0]
    return _MASTERY_REPS.get(gap(word_level, user_level), MASTERY_REPS_FAR)


# The production ladder's stages as fractions of a word's mastery bar, taken
# from the shape the flat bar of 10 had (reverse at 3, cloze at 5). They have to
# scale with the bar: pinning them to 3 and 5 while an at-level word masters at 6
# would leave exactly one typed rep before promotion, and a word below the user's
# level would be promoted before ever being typed at all.
_REVERSE_FRACTION = 0.3
_CLOZE_FRACTION = 0.5


def ladder_stages(mastery_target: int) -> tuple[int, int]:
    """(reverse_at, cloze_at) rep counts for a word with this mastery bar.

    Always leaves at least one rep in each stage, so even the shortest bar walks
    recognition -> reverse -> production rather than skipping straight to typing.
    """
    reverse_at = max(1, round(mastery_target * _REVERSE_FRACTION))
    cloze_at = max(reverse_at + 1, round(mastery_target * _CLOZE_FRACTION))
    return reverse_at, cloze_at


# Recalibration — the placement test is a one-minute guess, and people move.
# Promotion needs a body of evidence at the user's own level or harder; a
# handful of easy wins shouldn't push someone into material they can't read.
PROMOTE_MASTERED = 20
# Demotion is deliberately harder to trigger than promotion, and needs a real
# sample: being wrong is normal while learning, and yanking someone down after a
# bad evening would be both wrong and demoralising.
DEMOTE_MIN_ATTEMPTS = 40
DEMOTE_ACCURACY = 0.35


def recalibrated_level(
    current: str | None,
    mastered_at_or_above: int,
    attempts_at_level: int,
    correct_at_level: int,
) -> str | None:
    """The user's level revised from their actual record, or None to leave it.

    Only ever moves one step at a time: the counters that justify a jump are the
    same ones a single step will change, so stepping keeps the next decision
    honest instead of overshooting on one burst of activity.
    """
    level = normalize(current)
    if mastered_at_or_above >= PROMOTE_MASTERED:
        promoted = shift(level, 1)
        return promoted if promoted != level else None
    if attempts_at_level >= DEMOTE_MIN_ATTEMPTS:
        accuracy = correct_at_level / attempts_at_level
        if accuracy < DEMOTE_ACCURACY:
            demoted = shift(level, -1)
            return demoted if demoted != level else None
    return None


# Where the adaptive test starts. Beginning in the middle means a beginner
# finishes after two blocks (fail A2, fail A1) and an advanced learner after
# three, instead of everyone answering every level.
TEST_START_LEVEL = "A2"


def next_test_level(
    current: str, passed: bool, tested: set[str]
) -> tuple[str | None, str]:
    """One step of the placement staircase.

    Returns (level to test next, verdict so far). A `None` level means stop and
    take the verdict.

    Climbing while they pass and stopping at the first failure is what makes
    guessing expensive: reaching B2 means clearing A2, B1 and B2 in turn, so a
    lucky block no longer promotes anyone on its own.
    """
    pos = index(current)
    if passed:
        held = current
        if pos + 1 >= len(TEST_LEVELS):
            return None, held  # cleared the hardest level we test
        nxt = TEST_LEVELS[pos + 1]
        return (None, held) if nxt in tested else (nxt, held)
    # Failed here. Anything below that we already cleared is the answer;
    # otherwise step down and test that.
    for lower in reversed(TEST_LEVELS[:pos]):
        if lower in tested:
            return None, lower
    if pos == 0:
        return None, TEST_LEVELS[0]
    return TEST_LEVELS[pos - 1], TEST_LEVELS[0]


def block_passed(flags: list[bool]) -> bool:
    """Whether one level's block of questions counts as held."""
    return bool(flags) and sum(flags) / len(flags) >= TEST_PASS_RATIO
