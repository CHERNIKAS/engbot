"""Building a sentence: what counts as right, and what the answer was worth.

Two modes read the same exercise. The assisted one walks the learner through
`slots` — subject, then auxiliary, then verb form — where each choice narrows
what comes next. The typing one shows the Russian and takes whatever they
write. A topic starts assisted and is passed typed.

Three decisions shape the rest of the module.

**No fuzzy matching on the graded part.** `He work` and `He works` differ by one
character, and that character is the entire lesson. Any edit-distance tolerance
that forgives it would forgive exactly what the exercise exists to test. So the
strict check is exact, and a miss goes to the AI checker, which can tell a real
typo from a wrong form — the same route a mistyped word already takes.

**Attempts are immediate, not spaced.** A wrong word order is worth correcting
while the sentence is still in your head; two hours later it is a different
task. They cost value rather than blocking, so a card always closes and the
plan can never stick on one sentence.

**The topic score decays instead of accumulating.** An accumulator says
"learned" once and never asks again, which is how a topic could be passed and
long forgotten while still showing full marks. Each answer moves the score
toward itself, so it always describes how the learner answers *now* — and a
topic that has gone stale says so without anyone running a check.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, replace

MAX_ATTEMPTS = 3

# What one answer is worth, by the attempt it landed on. A first-attempt answer
# is the only one that proves unaided recall; the rest proves progressively
# less, which is exactly what a lower number should mean.
_ATTEMPT_CREDIT = {1: 1.0, 2: 0.5, 3: 0.25}

# A hint costs less than a wrong guess, and that ordering is the point rather
# than the number. The first pass had hints at half value, which made a hinted
# first attempt worth 0.5 against 0.6 for guessing wrong and then getting it —
# so the paying move was to tap something at random and correct it. In the
# assisted mode a random tap is free, and rewarding it is the opposite of what
# the constructor exists for.
#
# The ladder now only ever goes down: 1.0 clean, 0.7 hinted, 0.5 second try,
# 0.35 hinted second, 0.25 third.
HINT_MULTIPLIER = 0.7

# Never zero for an answer that eventually landed. Someone who needs the third
# attempt and a hint on every sentence would otherwise sit at a flat zero
# forever, with no way to see themselves improving.
MIN_CREDIT = 0.2

# How fast the topic score follows recent answers. At 0.15 the last handful of
# answers carry most of the weight and roughly twenty turn it over completely —
# about five days at four grammar cards a day. A starting point to calibrate on
# real answer data, not a constant anyone derived.
DECAY = 0.15

MAX_STARS = 5.0

_TRAILING_PUNCT = re.compile(r"[.!?,;:]+$")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'"})


def normalize(text: str | None) -> str:
    """A sentence reduced to what actually has to match.

    Case, spacing, the curly apostrophe a phone keyboard inserts, and a missing
    full stop are not the lesson. Word choice and word order are, and this
    leaves both untouched.
    """
    if not text:
        return ""
    cleaned = text.strip().translate(_APOSTROPHES)
    cleaned = _TRAILING_PUNCT.sub("", cleaned)
    return " ".join(cleaned.lower().split())


def matches(answer: str | None, expected: str, alternatives: list[str] | None = None) -> bool:
    """Whether this is the sentence, allowing every rendering we accept.

    `alternatives` carries the honest variants — «does not» beside «doesn't» —
    so writing it out in full is never punished as an error.
    """
    got = normalize(answer)
    if not got:
        return False
    accepted = {normalize(expected)} | {normalize(a) for a in (alternatives or [])}
    accepted.discard("")
    return got in accepted


def credit(attempt: int, hinted: bool = False) -> float:
    """What an answer landed on this attempt is worth, from 0 to 1.

    An attempt past the last one scores nothing: the sentence was shown, so
    there is nothing left to prove.
    """
    base = _ATTEMPT_CREDIT.get(attempt)
    if base is None:
        return 0.0
    if hinted:
        base *= HINT_MULTIPLIER
    return max(MIN_CREDIT, round(base, 2))


def attempts_left(attempt: int) -> int:
    return max(0, MAX_ATTEMPTS - attempt)


def update_score(previous: float | None, answer_credit: float, decay: float = DECAY) -> float:
    """The topic score after one answer.

    A moving average rather than a running total. The difference is the whole
    point: a total can only go up, so a topic passed in March still reads as
    passed in September. This follows recent answers, so stopping and
    forgetting shows up on its own, with no separate check to schedule.

    A brand-new topic starts at zero and climbs, which is honest — nothing has
    been shown yet.
    """
    base = 0.0 if previous is None else previous
    return round(base + (answer_credit - base) * decay, 4)


def stars(score: float | None) -> float:
    """The 0–5 figure shown on the topic, one decimal."""
    return round(max(0.0, min(1.0, score or 0.0)) * MAX_STARS, 1)


def slot_options(slots: list[dict], index: int) -> list[str]:
    """Choices for one step of the assisted mode, or empty past the end."""
    if index < 0 or index >= len(slots):
        return []
    return list(slots[index].get("options") or [])


def slot_correct(slots: list[dict], index: int) -> str:
    if index < 0 or index >= len(slots):
        return ""
    return str(slots[index].get("correct") or "")


def assembled(slots: list[dict], chosen: list[str]) -> str:
    """What the learner has built so far, for echoing back above the choices."""
    return " ".join(part for part in chosen if part).strip()


def is_complete(slots: list[dict], chosen: list[str]) -> bool:
    return len(chosen) >= len(slots) > 0


def full_answer(slots: list[dict]) -> str:
    """The sentence the slots build — used to check the assembled result
    against the same expectation the typing mode uses."""
    return " ".join(str(s.get("correct") or "") for s in slots).strip()


# ---- card text -------------------------------------------------------------
#
# Kept here with the rest of the constructor rather than in the handler: the
# card has real branching (two modes, a partial answer, attempts left) and that
# is worth unit-testing without a Telegram client. `app.domain.quiz_text`
# already sets the precedent for text helpers living in the domain.


def render_card(
    *,
    topic_title: str,
    score: float | None,
    ru: str,
    built: str = "",
    typing: bool = False,
    attempt: int = 1,
    hinted_prefix: str = "",
    plan_done: int = 0,
    plan_total: int = 0,
) -> str:
    """The constructor card, HTML-escaped.

    `built` is what the learner has assembled so far in the assisted mode; it
    is echoed back so the sentence stays visible as it grows, which is the
    whole reason tapping through slots is not just a slower multiple choice.

    Everything interpolated here can contain `<`, `>` or `&` — the Russian
    prompt and the English come from generated content, and a single unescaped
    angle bracket makes Telegram reject the whole message, which would look
    like the card silently failing to arrive.
    """
    head = f"📖 <b>{html.escape(topic_title)}</b>"
    if score is not None:
        head += f" · {stars(score)}"
    if plan_total:
        head += f" · {plan_done} / {plan_total}"

    parts = [head, "", html.escape(ru.strip())]

    if typing:
        parts.append("")
        parts.append("<i>Напиши по-английски.</i>")
        if hinted_prefix:
            parts.append(f"<i>Начало: {html.escape(hinted_prefix)}…</i>")
        if attempt > 1:
            parts.append(f"<i>Попытка {attempt} из {MAX_ATTEMPTS}.</i>")
    else:
        # A blank line holds the answer's place before the first tap, so the
        # card does not jump when the first word appears.
        parts.append("")
        parts.append(f"<b>{html.escape(built)}</b>" if built else "‎")
    return "\n".join(parts)


def render_result(
    *, ru: str, en: str, correct: bool, answer_credit: float, hint: str = ""
) -> str:
    """What replaces the card once it is settled.

    Always shows the right sentence, including after a correct answer: the
    learner may have reached it on the third attempt, and seeing it whole is
    the part that sticks.
    """
    mark = "✅" if correct else "❌"
    parts = [f"{mark} {html.escape(ru.strip())}", f"<b>{html.escape(en.strip())}</b>"]
    if hint:
        parts.append(f"<i>{html.escape(hint)}</i>")
    if correct and answer_credit < 1.0:
        parts.append(f"<i>Засчитано на {answer_credit:.1f} из 1.0</i>")
    return "\n".join(parts)


# ---- card state ------------------------------------------------------------


@dataclass(frozen=True)
class CardState:
    """Where the learner is inside one exercise.

    Immutable so every transition returns a new value: the state is round-
    tripped through Redis between taps, and a helper that mutated in place
    would appear to work locally while silently dropping the change on the way
    out.
    """

    chosen: tuple[str, ...] = ()
    attempt: int = 1
    hinted: bool = False
    typing: bool = False

    @property
    def slot_index(self) -> int:
        return len(self.chosen)

    @property
    def exhausted(self) -> bool:
        return self.attempt > MAX_ATTEMPTS

    def to_dict(self) -> dict:
        return {
            "chosen": list(self.chosen),
            "attempt": self.attempt,
            "hinted": self.hinted,
            "typing": self.typing,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "CardState":
        data = data or {}
        return cls(
            chosen=tuple(data.get("chosen") or ()),
            attempt=int(data.get("attempt") or 1),
            hinted=bool(data.get("hinted")),
            typing=bool(data.get("typing")),
        )


def choose(state: CardState, slots: list[dict], option_index: int) -> tuple[CardState, bool]:
    """Tap one option in the assisted mode. Returns (state, was_right).

    A wrong tap costs an attempt and leaves the slot open, rather than being
    written into the sentence and judged at the end. Correcting it now, with
    the choice still on screen, is the moment the learner can actually learn
    from — and a sentence assembled out of pieces they already know are wrong
    teaches nothing on the way to the verdict.
    """
    options = slot_options(slots, state.slot_index)
    if option_index < 0 or option_index >= len(options):
        return state, False
    picked = options[option_index]
    if normalize(picked) != normalize(slot_correct(slots, state.slot_index)):
        return replace(state, attempt=state.attempt + 1), False
    return replace(state, chosen=state.chosen + (picked,)), True


def undo(state: CardState) -> CardState:
    """Take back the last piece. Does not refund the attempt — those were spent
    on wrong taps, and giving them back would make «Ой, ошибся» a way to retry
    for free."""
    if not state.chosen:
        return state
    return replace(state, chosen=state.chosen[:-1])


def use_hint(state: CardState) -> CardState:
    """Mark the answer as helped. Idempotent: a second tap must not halve the
    value twice, and nothing stops a learner tapping it again."""
    return state if state.hinted else replace(state, hinted=True)


def miss(state: CardState) -> CardState:
    """A wrong typed answer — spend one attempt."""
    return replace(state, attempt=state.attempt + 1)


def to_typing(state: CardState) -> CardState:
    return replace(state, typing=True)


def hint_prefix(expected: str, reveal: int = 2) -> str:
    """The opening of the answer, for the typing mode.

    Two words rather than one: a single «She» narrows nothing, since almost
    every sentence in the set starts with a subject. Two reaches the auxiliary,
    which is where the actual decision lives.
    """
    words = (expected or "").split()
    return " ".join(words[:reveal])


# ---- topic thresholds ------------------------------------------------------
#
# Scores are 0..1; the card shows them ×5. These are starting points to
# calibrate against real answers, not values anyone derived — which is why they
# are named and tested by their ordering rather than by their magnitude.

# Where the assisted mode stops teaching. Below this the learner is still
# getting the paradigm wrong often enough that seeing the options is doing
# work; above it, the options are mostly confirming what they already know.
TO_TYPING = 0.80

# Passing. Only reachable in the typing mode, because the assisted mode cannot
# prove production — the pieces are on screen.
PASSED = 0.90

# A passed topic that falls below this is going stale and earns extra cards
# until it recovers. The gap between this and PASSED is deliberate: without it
# a single bad evening would flip a topic in and out of the schedule, and the
# list of finished topics would flicker.
STALE = 0.70

# The decay alone already forces roughly fifteen clean answers to reach PASSED,
# but leaving that implicit means a change to DECAY could quietly let a topic
# pass on three lucky ones. Stated so it cannot.
MIN_ANSWERS_TO_PASS = 20

STAGE_ASSISTED = "assisted"
STAGE_TYPING = "typing"
STAGE_PASSED = "passed"


def should_switch_to_typing(score: float | None, typing: bool) -> bool:
    """Whether to drop the tiles. One-way: see `UserGrammarTopic.typing`."""
    return not typing and (score or 0.0) >= TO_TYPING


def should_pass(score: float | None, answered: int, typing: bool) -> bool:
    """Whether the topic is finished.

    Requires the typing mode, so a topic can never be passed on the strength of
    picking from options — which is the whole reason the constructor replaced
    the gap-fill cards.
    """
    return typing and answered >= MIN_ANSWERS_TO_PASS and (score or 0.0) >= PASSED


def is_stale(score: float | None, passed_at_set: bool) -> bool:
    """Whether a finished topic has decayed enough to need attention again.

    Not "unpassed" — passing is not revoked. It just starts appearing in the
    day again until the score recovers, which is the same thing spaced
    repetition does for a word, applied to a rule.
    """
    return passed_at_set and (score or 0.0) < STALE


def place(state: CardState, piece: str) -> CardState:
    """Put a piece into the sentence without it being a choice.

    Used by the hint in the assisted mode: with the options already on screen
    there is nothing to reveal except the answer itself, so the help is to
    place it. The attempt is untouched — the hint already costs value, and
    charging for it twice would make asking worse than failing.
    """
    if not piece:
        return state
    return replace(state, chosen=state.chosen + (piece,))


def render_topic_list(rows: list[tuple[str, float | None, bool, bool]]) -> str:
    """The grammar syllabus with where the learner stands on each topic.

    `rows` is (title, score, typing, passed). Three states are worth telling
    apart and only three: passed, in progress, not started. A score on an
    untouched topic would read as «you scored zero», which is not what an
    unopened lesson means.
    """
    lines = ["📖 <b>Грамматика</b>", ""]
    current_marked = False
    for title, score, typing, passed in rows:
        if passed:
            lines.append(f"✅ {title} · {stars(score)}")
        elif score is not None:
            mode = "печать" if typing else "блоки"
            mark = "▶️" if not current_marked else "•"
            current_marked = True
            lines.append(f"{mark} <b>{title}</b> · {stars(score)} · {mode}")
        else:
            mark = "▶️" if not current_marked else "🔒"
            if not current_marked:
                current_marked = True
                lines.append(f"{mark} <b>{title}</b> · не начата")
            else:
                lines.append(f"{mark} {title}")
    lines.append("")
    lines.append(
        f"<i>Тема сдана при {stars(PASSED)} из {MAX_STARS} в режиме печати.</i>"
    )
    return "\n".join(lines)
