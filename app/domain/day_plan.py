"""What a learner is asked to do today, decided once and then held.

The push used to draw each card from a weighted lottery: repeat 60, review 22,
new 18, grammar 15. That is unknowable from the outside — you could not say
what today would contain, how much of it there was, or whether you were done.
Prod showed the cost plainly: the bot could deliver ~56 cards in an evening
window while the user answered ten, and the other forty-six were nudged three
times and dropped.

A plan replaces the lottery with a list: fixed composition, announced up front,
finished or not finished.

Two rules carry most of the design.

**A card counts as done when it is answered, right or wrong.** Getting it wrong
is already handled — spaced repetition brings the word back tomorrow — and
requiring a correct answer would let one hard word block the day forever. The
plan measures attendance, not accuracy.

**An unfinished plan is not replaced.** Yesterday's plan is today's plan until
it is closed. It does not expire (which would make a missed day pointless) and
it does not stack (which would greet a returning learner with a week of debt).
There is only ever one plan in flight.
"""

from __future__ import annotations

from dataclasses import dataclass

# Slots, in the order they are filled. Grammar and phrases are fixed: they are
# the parts of the day that would otherwise be crowded out, because review load
# grows without limit while they do not.
GRAMMAR_PER_DAY = 4
PHRASES_PER_DAY = 2

# New words are capped from both ends. The floor guarantees the learner always
# meets something new, however big the review backlog. The ceiling is the one
# that matters: without it day one is 24 new words, because nothing else exists
# yet to fill the plan — and the whole arithmetic of ~8 touches per word assumes
# they arrive spread out rather than dumped.
MIN_NEW_WORDS = 3
MAX_NEW_WORDS = 10

# Of the new words, roughly a third comes from the current theme and the rest
# from the frequency stream. Corpus rank alone would spend a beginner's first
# month on `organization` and `performance` — it ranks written English, and does
# not contain `apple` at all.
THEME_SHARE = 3

DEFAULT_SIZE = 28
MIN_SIZE = 8
MAX_SIZE = 40

# How the plan resizes itself. Deliberately asymmetric: growth needs a week of
# evidence, shrinking needs three days. Being too big is the failure that makes
# someone quit; being too small only costs a little progress.
GROW_AFTER_CLOSES = 7
SHRINK_AFTER_MISSES = 3
RESIZE_STEP = 2

REPEAT = "repeat"
GRAMMAR = "grammar"
PHRASE = "phrase"
NEW_WORD = "new_word"
NEW_THEME_WORD = "new_theme_word"
TRIAGE = "triage"
TEST = "test"


@dataclass(frozen=True)
class Composition:
    """How many cards of each kind today's plan asks for."""

    repeats: int
    grammar: int
    phrases: int
    new_frequency: int
    new_theme: int

    @property
    def total(self) -> int:
        return self.repeats + self.grammar + self.phrases + self.new_frequency + self.new_theme

    @property
    def new_words(self) -> int:
        return self.new_frequency + self.new_theme


def compose(
    size: int,
    due_repeats: int,
    grammar_available: int,
    phrases_available: int,
    new_available: int,
) -> Composition:
    """Today's plan, given what there is to draw from.

    Fill order is deliberate and is the whole ramp-up behaviour:

    1. repeats take what is due, but never the room reserved for new words —
       otherwise a large backlog would mean a day with nothing new in it;
    2. grammar and phrases take their fixed share;
    3. new words take whatever is left, up to the cap.

    On day one nothing is due, so new words fill their cap and the plan is
    small. As review load accumulates the repeats grow into the space and the
    plan reaches `size`. Nothing here needs to know which day it is.

    Every count is clamped by what actually exists: a plan that asks for cards
    the catalogue cannot supply would never be closeable.
    """
    size = max(MIN_SIZE, min(MAX_SIZE, size))
    grammar = min(GRAMMAR_PER_DAY, max(0, grammar_available))
    phrases = min(PHRASES_PER_DAY, max(0, phrases_available))

    reserved = grammar + phrases + MIN_NEW_WORDS
    repeats = max(0, min(due_repeats, size - reserved))

    room_for_new = size - grammar - phrases - repeats
    new_total = max(0, min(MAX_NEW_WORDS, room_for_new, new_available))

    new_theme = min(new_total // THEME_SHARE if new_total >= THEME_SHARE else 0, new_total)
    if new_total and not new_theme:
        new_theme = 1  # a theme word every day, even when the day is tiny
    new_frequency = new_total - new_theme

    return Composition(
        repeats=repeats,
        grammar=grammar,
        phrases=phrases,
        new_frequency=new_frequency,
        new_theme=new_theme,
    )


def next_size(size: int, consecutive_closes: int, consecutive_misses: int) -> int:
    """The plan size for tomorrow.

    Reads streaks rather than a rolling average so the change is explainable:
    "you have closed it a week running, adding two" is something the bot can
    say out loud, which matters — a plan that resizes silently looks broken.
    """
    if consecutive_misses >= SHRINK_AFTER_MISSES:
        return max(MIN_SIZE, size - RESIZE_STEP)
    if consecutive_closes >= GROW_AFTER_CLOSES:
        return min(MAX_SIZE, size + RESIZE_STEP)
    return size


def is_closed(done: int, total: int) -> bool:
    """A plan with nothing in it is closed, not pending: an empty plan would
    otherwise freeze forever and block every following day."""
    return done >= total


def remaining_percent(done: int, total: int) -> int:
    """How much of the plan is left, for «осталось добить N%».

    Rounded up while anything remains, so one unanswered card out of forty
    never reports as 0% left and reads as a bug.
    """
    if total <= 0 or done >= total:
        return 0
    left = total - done
    return max(1, round(100 * left / total))


# What each slot kind is called when the plan is shown. Declared here, next to
# the kinds themselves, so the push card and the «Сегодня» screen cannot drift
# into describing the same day differently.
KIND_LABELS: tuple[tuple[str, str], ...] = (
    (REPEAT, "🔁 Повторить"),
    (GRAMMAR, "📖 Грамматика"),
    (NEW_THEME_WORD, "🆕 Слова по теме"),
    (NEW_WORD, "🆕 Новые слова"),
    (PHRASE, "💬 Фразы"),
    (TRIAGE, "🗂 Разбор темы"),
    (TEST, "📝 Проверка темы"),
)


def render(counts: dict[str, int], done: int | None = None) -> str:
    """The day as a list of what is in it.

    `done` turns the announcement into a progress view: the same text the
    learner was shown in the morning, with how far they have got. Kept as one
    function because two renderers would eventually disagree about what the
    day contains, and the learner would notice before we did.
    """
    total = sum(counts.values())
    head = f"📅 <b>План на сегодня</b> · {total} карточек"
    if done is not None:
        head += f"\n<b>{done}</b> из <b>{total}</b> сделано"
    parts = [head, ""]
    parts.extend(
        f"{label} — {counts[kind]}" for kind, label in KIND_LABELS if counts.get(kind)
    )
    parts.append("")
    if done is not None and is_closed(done, total):
        parts.append("<i>План на сегодня закрыт. Новый соберётся завтра 🌿</i>")
    elif done is not None:
        parts.append(f"<i>Осталось добить {remaining_percent(done, total)}%.</i>")
    else:
        parts.append("<i>Можно растянуть на весь день, можно закрыть за раз.</i>")
    return "\n".join(parts)


# What a card says about its place in the day, above everything else on it.
#
# Only the constructor used to carry this, so a word card arrived as a ping from
# nowhere while a grammar card looked like part of a lesson. One function builds
# it for every kind, because two of them would drift and the learner would be
# told two different things about the same day.
SLOT_HEADS: dict[str, str] = {
    REPEAT: "🔁 Повтор",
    NEW_WORD: "🆕 Новое слово",
    NEW_THEME_WORD: "🆕 Слово по теме",
    PHRASE: "💬 Фраза",
    GRAMMAR: "📖 Грамматика",
    TRIAGE: "🗂 Разбор темы",
    TEST: "📝 Проверка",
}


def card_head(kind: str, done: int = 0, total: int = 0, extra: str = "") -> str:
    """The one-line header: what this card is, and where it sits in the day.

    `extra` is for whatever only one kind has — the constructor's topic title
    and mark. Absent counters render the label alone rather than «0 / 0», which
    would read as a plan that lost its contents.
    """
    parts = [SLOT_HEADS.get(kind, "🔔 Карточка")]
    if extra:
        parts.append(extra)
    if total > 0:
        parts.append(f"{done} / {total}")
    return " · ".join(parts)
