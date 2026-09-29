from __future__ import annotations

import html
import json
import random
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.push import (
    SNOOZE_LABELS,
    constructor_slots_kb,
    constructor_typing_kb,
    test_offer_kb,
    triage_kb,
    push_card_kb,
    push_cloze_card_kb,
    push_grammar_card_kb,
    push_leech_kb,
    push_rule_kb,
)
from app.bot.texts import (
    PUSH_ANSWER_ALMOST,
    PUSH_ANSWER_CORRECT,
    PUSH_ANSWER_DEGRADED,
    PUSH_ANSWER_WRONG,
    PUSH_ANSWER_WRONG_HINT,
    PUSH_CARD,
    PUSH_CARD_CLOZE,
    PUSH_CARD_REVERSE,
    PUSH_CARD_TYPE_IN,
    PUSH_GRAMMAR_CARD,
    PUSH_HIDDEN,
    PUSH_MASTERED_KNOWN,
    PUSH_LEECH_KEPT,
    PUSH_LEECH_PARKED,
    PUSH_LEECH_PROMPT,
    PUSH_RECAP_EXAMPLE,
    PUSH_RECAP_MASTERED,
    PUSH_RECAP_MASTERED_NOW,
    PUSH_RECAP_NEXT,
    PUSH_RECAP_PROGRESS,
    PUSH_RECAP_PROGRESS_FLAT,
    PUSH_RECAP_TRANSLATION,
    PUSH_RECAP_TYPED_LEFT,
    PUSH_RECAP_WORD,
    PUSH_RULE_CARD,
    PUSH_SNOOZED,
    PUSH_STALE,
    TRIAGE_DONE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult, WordStatus
from app.domain import mastery
from app.domain.levels import ladder_stages, mastery_reps
from app.domain.study_drill import is_typing_correct
from app.domain.models import User, UserTrack
from app.domain.push import in_window, normalize_window
from app.domain.quiz_text import strip_latin_hints
from app.domain.push_nudges import nudge_line
from app.infrastructure.repositories.analytics import AnalyticsRepository
from app.infrastructure.repositories.grammar import GrammarRepository
from app.infrastructure.repositories.reviews import GrammarReviewRepository, WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.logging_setup import get_logger
from app.services.analytics import (
    EVENT_ANSWER_GRADED,
    EVENT_WORD_MASTERED,
    Analytics,
)
from app.services.answer_check import AnswerCheckService
from app.services.regrade import ParkedAnswer, RegradeQueue
from app.services.progress_service import ProgressService
from app.domain import constructor as ctor
from app.domain import day_plan as plan_rules
from app.domain import day_summary
from app.domain import topic_test
from app.domain import triage
from app.domain.models import GrammarTopic
from app.infrastructure.repositories.constructor import ConstructorRepository
from app.services.constructor_service import ConstructorService
from app.services.day_plan_service import DayPlanService
from app.services.repetition_service import MASTERED_REPS_NORMAL, apply_review

log = get_logger("push")

_KEY = "push:{user_id}"
_TTL = 172_800  # 2 days
_TRACK = LearningTrack.ENGLISH

# Consecutive wrong answers before the bot offers to postpone a word (leech
# detection — one impossible word shouldn't clog a slot in the active pool).
LEECH_THRESHOLD = 6
LEECH_PARK_DAYS = 7

# Ignored-card policy: a card not answered is re-pushed a few times, then DROPPED
# (an ignore is "not now", not a wrong answer — SR state untouched). Intervals
# back off so one card can't monopolise the window.
PUSH_MAX_ATTEMPTS = 3  # nudges before giving up (then move on)

# Per-user push-window overrides, keyed by telegram_id. A hand-set schedule for
# a specific user that wins over their in-app window setting. (start, end) in
# local hours, [start, end). Remove an entry to hand the window back to the user.
PUSH_WINDOW_OVERRIDES: dict[int, tuple[int, int]] = {
    553133186: (14, 21),  # @tannache — custom 14:00–21:00
}


def _retry_after(attempts: int) -> float:
    """Seconds until the next nudge — backs off 10, 20, 40 min (±20% jitter)."""
    base_min = min(10 * (2 ** (max(1, attempts) - 1)), 40)
    return base_min * 60.0 * random.uniform(0.8, 1.2)


# Past this a duration is not a measurement of anything — a card cannot be
# answered six hours after it was sent under the nudge cycle, so such a value
# means a clock jump, not a slow learner. Recorded as unknown instead.
_MAX_RESPONSE_SECONDS = 6 * 3600


def _timing(inflight: dict, now_ts: float) -> tuple[int | None, int]:
    """(milliseconds taken to answer, which push it was answered on).

    The clock restarts on every re-push: the card the user acted on is the one
    they last saw, so timing a nudged card from its first send would measure
    the phone lying face-down rather than the answer. `attempts` is what keeps
    the sample honest — 1 means answered on the first push, and only those rows
    say anything about how much attention a card actually costs.
    """
    attempts = int(inflight.get("attempts", 0)) + 1
    sent = inflight.get("sent_ts")
    if not sent:
        return None, attempts
    elapsed = now_ts - float(sent)
    if elapsed < 0 or elapsed > _MAX_RESPONSE_SECONDS:
        return None, attempts
    return int(elapsed * 1000), attempts


# Stream weights so grammar is a deliberate MINORITY (~1 in 6), not a coin flip
# that wins whenever the word streams are momentarily empty. We draw a weighted
# order and take the first stream that yields a card (so a dead stream doesn't
# waste the tick, and can't hand its share to grammar).
# `phrase` is small on purpose. A phrasebook entry is learned whole and cannot
# be typed into a gap, so it proves less per card than a word does — but the
# frequency ordering gives phrases no place at all (they have no corpus rank),
# and a learner three days in should still be able to say hello.
STREAM_WEIGHTS = {"repeat": 60, "review": 22, "new": 18, "grammar": 15, "phrase": 8}


def _weighted_order(streams: list[str]) -> list[str]:
    """A weighted-random permutation of the eligible streams."""
    pool = list(streams)
    out: list[str] = []
    while pool:
        weights = [STREAM_WEIGHTS.get(s, 1) for s in pool]
        pick = random.choices(pool, weights=weights, k=1)[0]
        out.append(pick)
        pool.remove(pick)
    return out

# Production ladder: a word climbs card types as it's answered correctly, so
# production is gated behind successful recognition (testing-effect boundary
# condition — retrieval must succeed for the benefit to stick). The stage is
# derived from repetitions_count (net correct, LAPSE_DROP on a miss) — no extra
# column needed; a miss naturally drops the word down the ladder. The stage
# boundaries are no longer fixed — they scale with the word's own mastery bar
# (levels.ladder_stages), which now depends on how far the word sits from the
# user's level. At the legacy bar of 10 they still land on 3 and 5:
#   reps 0-2 → recognition (EN→RU choice)
#   reps 3-4 → reverse     (RU→EN choice)
#   reps 5-9 → cloze       (type the word into an English sentence)
CARD_RECOGNITION = "recognition"
CARD_REVERSE = "reverse"
CARD_CLOZE = "cloze"
# Typed production without a sentence to blank: write the whole thing from the
# translation. Phrasebook entries are already whole sentences with nowhere to
# hide a gap, and until this existed they fell back to a choice card — which
# meant 106 phrases could never be produced at all, only recognised.
CARD_TYPE_IN = "type_in"


_CARD_ANSWER_KIND = {
    CARD_RECOGNITION: mastery.RECOGNITION,
    CARD_REVERSE: mastery.REVERSE,
    CARD_CLOZE: mastery.TYPED_EXACT,
    CARD_TYPE_IN: mastery.TYPED_EXACT,
}


def _answer_kind(card_type: str | None, correct: bool) -> str:
    """Translate "which card was it, and did they get it right" into the kind
    the score table understands. Near-miss kinds (typo / synonym / grammar) come
    from the AI check and are not produced here."""
    if not correct:
        return mastery.WRONG
    return _CARD_ANSWER_KIND.get(card_type or "", mastery.RECOGNITION)


def _leech_after(consecutive_wrong_before: int, correct: bool, was_mastered: bool) -> tuple[int, bool]:
    """Update the consecutive-miss counter for a word and decide whether it just
    became a leech. Mastered words never become leeches (they ride a 0–5 score,
    not the active-learning track). Returns (new_counter, offer_to_postpone)."""
    if correct or was_mastered:
        return 0, False
    n = (consecutive_wrong_before or 0) + 1
    return n, n >= LEECH_THRESHOLD


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _minutes(a: int, b: int) -> float:
    return random.randint(a, b) * 60.0


_CLOZE_ANSWER_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]*$")


def _looks_like_cloze_answer(text: str) -> bool:
    """Whether this is the shape a cloze blank expects — a single English word."""
    return bool(_CLOZE_ANSWER_RE.match(text.strip()))


_TYPED_CARDS = (CARD_CLOZE, CARD_TYPE_IN)
_QUICK_ADD_MARKS = ("|", " - ", " — ", " – ", "	")


def _looks_like_typed_answer(text: str, card_type: str | None) -> bool:
    """Whether this message is an answer to the card in flight.

    The test asks whether the text looks like English and carries none of the
    marks of a quick-add — which always pairs a word with a Russian translation,
    so it needs a separator or Cyrillic to be one.

    Cloze used to demand a SINGLE English word here, reasoning that a blank
    holds one token. But someone who types "might be" into a blank has plainly
    answered the card, and the strict rule handed that to quick-add instead:
    the card stayed in flight nudging them, and they got an unwanted
    «Добавить "might be"?» prompt. A two-word answer to a one-word blank is a
    WRONG answer, and it belongs in the grader — where the checker can still
    credit a near miss — not in the word list.
    """
    body = (text or "").strip()
    if not body:
        return False
    if any(mark in body for mark in _QUICK_ADD_MARKS) or "\n" in body:
        return False
    if any("Ѐ" <= ch <= "ӿ" for ch in body):
        return False  # Russian in the answer means they typed the translation
    return any(ch.isalpha() for ch in body)


def _push_day(local: datetime, window_start: int) -> str:
    """The 'push day' a moment belongs to — rolls at the window's start hour, not
    calendar midnight. An overnight window (e.g. 16→02) runs past midnight, so a
    plain date() reset at 00:00 would swap the in-flight card mid-answer and
    re-zero new_today inside one evening session. Anchoring the day to the window
    start keeps one session on one key."""
    d = local.date()
    if local.hour < window_start:
        d = d - timedelta(days=1)
    return d.isoformat()


def _days_ago_phrase(last_reviewed_at, now: datetime | None = None) -> str | None:
    """'сегодня' / 'вчера' / 'N дн назад' for a last-review time, or None."""
    if not last_reviewed_at:
        return None
    now = now or datetime.now(timezone.utc)
    days = (now.date() - last_reviewed_at.astimezone(timezone.utc).date()).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "вчера"
    return f"{days} дн назад"


def _times(n: int) -> str:
    """«раз» / «раза» — Russian picks the form from the last digit, except in
    the teens, where everything takes the plural."""
    if 11 <= n % 100 <= 14:
        return "раз"
    return "раза" if 2 <= n % 10 <= 4 else "раз"


def _score_of(uw) -> float:
    """Progress toward mastery, for whatever kind of item this is.

    Words carry a weighted `learning_score` (a typed answer is worth more than
    a four-option guess). Grammar items have no such column — they ride raw
    repetitions — and reading the word field off one crashed every grammar card
    before it could be sent.
    """
    score = getattr(uw, "learning_score", None)
    if score is None:
        return float(getattr(uw, "repetitions_count", 0) or 0)
    return float(score)


def _percent(uw, target: tuple[float, int] | None = None) -> int:
    """How far along the item is toward its mastery bar, 0-100."""
    target_score = (target or (float(MASTERED_REPS_NORMAL), 0))[0]
    if not target_score:
        return 0
    return min(100, round(100 * _score_of(uw) / target_score))


def _in_days_phrase(next_review_at, now: datetime | None = None) -> str | None:
    """'сегодня' / 'завтра' / 'через N дн' for the next scheduled sighting."""
    if not next_review_at:
        return None
    now = now or datetime.now(timezone.utc)
    days = (next_review_at.astimezone(timezone.utc).date() - now.date()).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    return f"через {days} дн"


def _progress_line(
    uw,
    now: datetime | None = None,
    target: tuple[float, int] | None = None,
    typing_now: bool = False,
) -> str:
    """Small progress hint under the word on a push card.

    Says how far along in words, not in fractions. The first cut printed
    "4.5 / 9.5 · 2 / 5" — three raw numbers legible to whoever wrote the scoring
    table and to nobody else. A percentage answers "how close am I", and the
    typed requirement is only worth a line while it's still the thing in the
    way; once it's met, saying so is noise.

    `typing_now` is True on the card where the user can actually type. Elsewhere
    the requirement is only mentioned once it's the *sole* thing left — asking
    someone to "напечатать ещё 3 раза" under a card with four buttons and no
    text field is asking for something they can't do from where they're standing.

    The miss count and last-seen stay: a bare number reads as a lie without
    them ("I know this, why half?"), and "you missed it twice, last seen 9 days
    ago" explains it instead of just asserting it.
    """
    if uw.status == WordStatus.MASTERED.value:
        return f"⭐ Выучено на {uw.mastery_score:.1f} из 5"

    target_score, needed_production = target or (float(MASTERED_REPS_NORMAL), 0)
    parts = [f"🌱 {_percent(uw, target)}%"]

    score = _score_of(uw)
    typed = getattr(uw, "production_count", 0) or 0
    blocking = needed_production and typed < needed_production
    if blocking and (typing_now or score >= target_score):
        left = needed_production - typed
        parts.append(f"✍️ напечатать ещё {left} {_times(left)}")

    if (uw.mistakes_count or 0) > 0:
        parts.append(f"❌ ошибок: {uw.mistakes_count}")
    seen = _days_ago_phrase(uw.last_reviewed_at, now)
    if seen:
        parts.append(seen)
    return "  ·  ".join(parts)


@dataclass(frozen=True)
class AnswerOutcome:
    """What settling an answer produced, for the caller to render."""

    leech_writing: str | None = None
    recap: str = ""


def _recap(
    uw,
    word,
    *,
    before_percent: int,
    was_mastered: bool,
    correct: bool,
    target: tuple[float, int] | None = None,
    now: datetime | None = None,
) -> str:
    """What the card shows under the verdict once the answer is out.

    A bare "✅ Верно! 🎉" discards everything the card was carrying: which word
    it even was, and how close it stands to being learned. The user answers a
    dozen of these a day and cannot tell one from another afterwards.

    So the reveal repeats the pair, moves the progress line to a before → after
    (a tap that changes nothing on screen reads as a tap that did nothing), and
    says when the word comes back. The example sentence appears only on a miss:
    that is when the context is worth reading, and on a hit it is just length.

    Pure so the formatting is testable without a bot or a session.
    """
    lines: list[str] = []
    translation = (uw.custom_translation or word.translation or "").strip()
    if correct:
        lines.append(PUSH_RECAP_WORD.format(writing=html.escape(word.writing or "")))
    elif translation:
        lines.append(PUSH_RECAP_TRANSLATION.format(translation=html.escape(translation)))
    if not correct and (word.example_sentence or "").strip():
        lines.append(PUSH_RECAP_EXAMPLE.format(sentence=html.escape(word.example_sentence.strip())))

    mastered_now = uw.status == WordStatus.MASTERED.value
    if mastered_now and not was_mastered:
        lines.append(PUSH_RECAP_MASTERED_NOW)
    elif mastered_now:
        lines.append(PUSH_RECAP_MASTERED.format(score=f"{uw.mastery_score:.1f}"))
    else:
        after = _percent(uw, target)
        progress = (
            PUSH_RECAP_PROGRESS_FLAT.format(after=after)
            if after == before_percent
            else PUSH_RECAP_PROGRESS.format(before=before_percent, after=after)
        )
        # Same rule as the card's own progress line: the typed requirement is
        # worth naming only once it is the sole thing left. Under a 53% bar it
        # is just one more number nobody asked for.
        target_score, needed = target or (0.0, 0)
        typed = uw.production_count or 0
        if needed and typed < needed and (uw.learning_score or 0) >= target_score:
            left = needed - typed
            progress += "  ·  " + PUSH_RECAP_TYPED_LEFT.format(n=left, times=_times(left))
        lines.append(progress)

    when = _in_days_phrase(uw.next_review_at, now)
    if when:
        lines.append(PUSH_RECAP_NEXT.format(when=when))
    # Blank line between the verdict and the recap: the verdict can already
    # carry a hint line of its own, and stacking everything unbroken reads as
    # one wall of symbols.
    return "\n\n" + "\n".join(lines) if lines else ""


# Card rendering --------------------------------------------------------------

_CLOZE_INFLECT = r"(?:s|es|ed|d|ing|ly|er|est)?"


def _mask_target(sentence: str, target: str) -> str | None:
    """Replace the target word (+ basic inflections) in `sentence` with ___ for a
    cloze card. Returns None when the word isn't found in a maskable form (e.g.
    an irregular like 'went' for 'go') — those words skip the cloze rung."""
    if not sentence or not target:
        return None
    pattern = re.compile(rf"\b{re.escape(target)}{_CLOZE_INFLECT}\b", re.IGNORECASE)
    masked, n = pattern.subn("___", sentence)
    return masked if n > 0 else None


def _format_word_card(writing: str, abstract_en: str | None, abstract_ru: str | None, progress: str) -> str:
    """Render the word push card. Includes a paired EN/RU abstract example
    underneath the question when both are present — these use synonyms /
    paraphrase so the target word isn't in the sentence (no spoilers). If
    either side is missing the example is skipped: better no hint than a
    half-baked one."""
    parts = [PUSH_CARD.format(word=html.escape(writing))]
    if abstract_en and abstract_ru:
        parts.append(f"📝 <i>{html.escape(abstract_en)}</i>")
        parts.append(f"<i>↳ {html.escape(abstract_ru)}</i>")
    parts.append(f"<i>{progress}</i>")
    return "\n".join(parts)


class PushService:
    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot | None = None) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot
        self._uw = UserWordRepository(session)
        self._grammar = GrammarRepository(session)
        self._reviews = WordReviewRepository(session)
        self._grammar_reviews = GrammarReviewRepository(session)
        self._checker = AnswerCheckService(redis)
        self._analytics = Analytics(AnalyticsRepository(session))
        self._regrade = RegradeQueue(redis)
        self._s = get_settings()

    # ---- state ----

    async def _load(self, user_id: int) -> dict:
        raw = await self._redis.get(_KEY.format(user_id=user_id))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    async def _save(self, user_id: int, state: dict) -> None:
        await self._redis.set(_KEY.format(user_id=user_id), json.dumps(state, ensure_ascii=False), ex=_TTL)

    async def _claim_answer(self, user_id: int, msg_id: int | None) -> bool:
        """Atomically claim a card's answer so a double-tap (or typed-answer +
        give-up) can't apply SR twice. Keyed on the card's MESSAGE id — unique
        per sent card, so a re-served word (new message) is never falsely
        blocked, but two taps on the SAME card race for one SET NX and only the
        first wins. TTL comfortably outlives the answer, well under the gap
        before the same word could be re-served as a new message."""
        if not msg_id:
            return True  # nothing to key on — don't block (shouldn't happen)
        key = f"pushans:{user_id}:{msg_id}"
        return bool(await self._redis.set(key, "1", nx=True, ex=600))

    def _window(self, user: User, ut: UserTrack) -> tuple[int, int]:
        override = PUSH_WINDOW_OVERRIDES.get(user.telegram_id)
        if override is not None:
            return normalize_window(
                override[0], override[1],
                min_hours=self._s.push_min_window_hours,
                default=(self._s.push_default_window_start, self._s.push_default_window_end),
            )
        s = ut.settings or {}
        return normalize_window(
            int(s.get("push_ws", self._s.push_default_window_start)),
            int(s.get("push_we", self._s.push_default_window_end)),
            min_hours=self._s.push_min_window_hours,
            default=(self._s.push_default_window_start, self._s.push_default_window_end),
        )

    # ---- worker tick ----

    async def run_all(self) -> int:
        # Push-learning is the main mode — on for every onboarded user.
        from app.infrastructure.repositories.user_tracks import UserTrackRepository
        from app.infrastructure.repositories.users import UserRepository

        if self._bot is None:
            return 0
        user_repo = UserRepository(self._session)
        ut_repo = UserTrackRepository(self._session)
        # Capture ids up front as plain ints, and re-fetch each user FRESH per
        # iteration. A per-user rollback (e.g. on a blocked user) expires every
        # ORM object in the session; touching an expired attribute (user.id)
        # then triggers a SYNC lazy-load → sqlalchemy MissingGreenlet, which is
        # NOT a TelegramForbiddenError, so it escapes the handler and aborts the
        # WHOLE worker tick. That silently broke delivery for everyone after the
        # first blocked user. Fresh fetch by plain id avoids the expired access.
        user_ids = [u.id for u in await user_repo.list_for_push()]
        pushed = 0
        skipped: list[int] = []
        for uid in user_ids:
            user = await user_repo.get(uid)
            ut = await ut_repo.get(uid, _TRACK)
            if user is None or ut is None:
                log.info("push_skipped", uid=uid, why="no_track")
                skipped.append(uid)
                continue
            if (ut.settings or {}).get("push_blocked"):
                # Blocked users vanished from the log entirely, so «this user
                # gets nothing» and «the worker is broken» looked identical
                # while reading it. Counted here and reported once per tick
                # rather than per user, to stay one line.
                skipped.append(uid)
                continue  # user blocked the bot — stop trying (cleared on /start)
            # No placement gate any more. It used to hold everyone without a
            # level, on the grounds that cards picked without one are picked
            # from a guess — true, but the guess it protected against was
            # `DEFAULT_LEVEL = "A2"`, which is what an empty level still reads
            # as everywhere else. The level is now derived from mastered words
            # at the start of `ensure_plan`, before anything is chosen, so a
            # learner arrives here with A1 rather than with nothing.
            # Commit per user: a tick can write (e.g. marking a grammar rule
            # seen), so one user's failure must not poison the shared transaction.
            try:
                if await self.run_tick(user, ut):
                    pushed += 1
                await self._session.commit()
            except TelegramForbiddenError:
                # Blocked mid-send — flag the user so we don't spam the worker.
                await self._session.rollback()
                fresh = await ut_repo.get(uid, _TRACK)
                if fresh is not None:
                    fresh.settings = {**(fresh.settings or {}), "push_blocked": True}
                    await self._session.commit()
                log.info("push_disabled_blocked", uid=uid)
            except Exception:  # noqa: BLE001
                await self._session.rollback()
                # log.exception keeps the traceback — a per-user logic bug that
                # silently disables one user's pushes every tick must be
                # diagnosable (this blind spot hid the recent MissingGreenlet).
                log.exception("push_tick_failed", uid=uid)
        if skipped:
            log.info("push_skipped_users", uids=skipped, count=len(skipped))
        return pushed

    async def run_tick(self, user: User, ut: UserTrack) -> bool:
        ws, we = self._window(user, ut)
        now = datetime.now(timezone.utc)
        local = now.astimezone(_tz(user.timezone))
        now_ts = now.timestamp()
        today = _push_day(local, ws)  # rolls at window start, not midnight

        state = await self._load(user.id)
        if state.get("day") != today:
            # Yesterday's card (+ any rule message) stays in chat with live
            # buttons after the day rolls over — tidy it so the user doesn't tap
            # a ghost card the next morning and get a stale-callback.
            prev = state.get("inflight") or {}
            for k in ("msg_id", "rule_msg_id"):
                mid = prev.get(k)
                if mid:
                    await self._delete(user.telegram_id, int(mid))
            state = {"day": today, "next_ts": 0.0, "inflight": None, "new_today": 0}
            # The level is re-derived here rather than inside `ensure_plan`,
            # which is where it used to live. `ensure_plan` returns an open plan
            # before reaching that point, so a learner whose plan stayed open —
            # one had an unfinished plan from six days earlier — never had their
            # level recomputed at all. Production showed it: a stored B2 sat
            # untouched while every newly-created plan derived A1 correctly.
            await DayPlanService(self._session).refresh_level(user, _TRACK)
            await self._session.commit()

        win = in_window(local.hour, ws, we)
        inflight = state.get("inflight")

        # ---- a card is waiting for an answer: keep nudging the SAME card until
        #      the user replies (the "force"); replace the old message each time.
        #      Each re-push carries an escalating "stop ignoring me" line.
        if inflight is not None:
            sent = False
            if win and now_ts >= inflight.get("retry_ts", 0):
                attempts = int(inflight.get("attempts", 0)) + 1
                if attempts > PUSH_MAX_ATTEMPTS:
                    # Given up nagging this card — drop it and move on. An ignore
                    # is "not now", NOT a wrong answer, so SR state is untouched.
                    old_msg_id = inflight.get("msg_id")
                    if old_msg_id:
                        await self._delete(user.telegram_id, old_msg_id)
                    state["last"] = {"kind": inflight.get("kind", "word"), "id": int(inflight.get("id", 0))}
                    # An abandoned card has to count as shown, or it is chosen
                    # again on the next turn and the "give up after three
                    # nudges" rule becomes a counter reset. Word cards are
                    # covered by `state["last"]` above; the constructor keeps
                    # its own recency list in the database.
                    dropped = inflight.get("kind")
                    if dropped == "phrase" and inflight.get("topic_id"):
                        await ConstructorRepository(self._session).note_shown(
                            user.id, int(inflight["topic_id"]), int(inflight.get("id", 0))
                        )
                        await self._session.commit()
                    elif dropped == "test" and inflight.get("topic_id"):
                        await ConstructorRepository(self._session).defer_test(
                            user.id, int(inflight["topic_id"])
                        )
                        await self._session.commit()
                    elif dropped == "triage":
                        # The batch is rebuilt from the same unmarked words, so
                        # an ignored one comes straight back. Hold it off until
                        # tomorrow rather than re-offering the same screenful.
                        state["triage_skip_day"] = state.get("day")
                    state["inflight"] = None
                    state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
                    log.info(
                        "push_card_abandoned",
                        uid=user.id,
                        kind=inflight.get("kind"),
                        id=inflight.get("id"),
                        attempts=attempts - 1,
                    )
                    await self._save(user.id, state)
                    return False
                inflight["attempts"] = attempts
                new_msg_id, _o, _c = await self._send_card(
                    user,
                    inflight.get("kind", "word"),
                    int(inflight.get("id", inflight.get("uw_id", 0))),
                    options_override=inflight.get("options"),
                    prefix=nudge_line(attempts),
                    card_type=inflight.get("ctype", CARD_RECOGNITION),
                    attempt=attempts,
                )
                if new_msg_id:
                    old_msg_id = inflight.get("msg_id")
                    if old_msg_id:
                        await self._delete(user.telegram_id, old_msg_id)
                    inflight["msg_id"] = new_msg_id
                    # Restart the answer clock: this re-push is the card the
                    # user will actually act on (see _timing).
                    inflight["sent_ts"] = now_ts
                    inflight["retry_ts"] = now_ts + _retry_after(attempts)
                    sent = True
            if not sent:
                self._log_idle(
                    user,
                    state,
                    "awaiting_answer",
                    kind=inflight.get("kind"),
                    id=inflight.get("id"),
                    retry_in_s=round(inflight.get("retry_ts", 0) - now_ts),
                )
            await self._save(user.id, state)
            return sent

        # ---- no card pending: gated by the window + the post-answer gap ----
        if not win or now_ts < state.get("next_ts", 0.0):
            # Silence has to be distinguishable from breakage. Without this line
            # a quiet hour and a dead worker look identical from the outside.
            self._log_idle(
                user,
                state,
                "outside_window" if not win else "gap",
                wait_s=0 if not win else round(state.get("next_ts", 0.0) - now_ts),
            )
            await self._save(user.id, state)
            return False

        # ---- a grammar rule waiting to be introduced? show it once, first ----
        rule_topic = await self._grammar.pending_rule(user.id, _TRACK)
        if rule_topic is not None:
            msg_id = await self._raw_send(
                user.telegram_id,
                PUSH_RULE_CARD.format(title=html.escape(rule_topic.title), rule=rule_topic.rule),
                push_rule_kb(),
                uid=user.id,
                kind="rule",
                obj_id=rule_topic.id,
            )
            if msg_id:
                await self._grammar.mark_rule_seen(user.id, rule_topic.id)
                state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
            await self._save(user.id, state)
            return msg_id is not None

        # ---- the day's plan decides what comes next ----
        #
        # This replaced a weighted lottery — repeat 60, review 22, new 18,
        # grammar 15 — drawn afresh on every tick. Nothing about that was
        # knowable from outside: the learner could not be told what today held,
        # how much of it there was, or whether they were finished. Prod showed
        # what it cost: the bot could push ~56 cards into an evening window
        # against ten answers, nudging the rest three times and dropping them.
        plan_service = DayPlanService(self._session)
        plan, opened = await plan_service.ensure_plan(user, _TRACK, date.fromisoformat(today))
        if plan is None:
            self._log_idle(user, state, "nothing_to_study")
            await self._save(user.id, state)
            return False
        await self._session.commit()

        if opened:
            # The plan card is the day's only announcement. It is sent before
            # the first exercise so the learner agrees to a known amount of
            # work rather than discovering its size by reaching the end.
            await self._raw_send(
                user.telegram_id, self._plan_card(plan), None, uid=user.id, kind="plan", obj_id=plan.id
            )
            state["next_ts"] = now_ts + _minutes(
                self._s.push_gap_min_minutes, self._s.push_gap_max_minutes
            )
            await self._save(user.id, state)
            return True

        progress = plan_service.progress(plan)
        if progress.closed:
            self._log_idle(user, state, "plan_closed", done=progress.done, total=progress.total)
            await self._close_day(user, plan, plan_service)
            await self._save(user.id, state)
            return False

        kind = plan_service.next_kind(plan)
        if kind is None:
            self._log_idle(user, state, "plan_exhausted", done=progress.done, total=progress.total)
            await self._save(user.id, state)
            return False

        sent = await self._serve(user, ut, kind, progress.done, progress.total, state, now_ts)
        if not sent:
            # The slot cannot be filled — the theme ran out, every topic is
            # passed, nothing is due. Tick it off rather than retrying forever:
            # an unfillable slot holds the plan open, and an open plan is never
            # replaced.
            log.info("push_slot_unfillable", uid=user.id, kind=kind, done=progress.done, total=progress.total)
            await plan_service.mark_done(plan, kind)
            await self._session.commit()
        await self._save(user.id, state)
        return sent

    async def _serve(
        self,
        user: User,
        ut: UserTrack,
        kind: str,
        done: int,
        total: int,
        state: dict,
        now_ts: float,
    ) -> bool:
        """Send the card this slot calls for. False when it cannot be filled."""
        if kind == plan_rules.TRIAGE:
            return await self._send_triage(user, state, now_ts)
        if kind == plan_rules.TEST:
            return await self._send_test(user, state, now_ts)
        if kind == plan_rules.GRAMMAR:
            return await self._send_constructor(
                user, state, now_ts, plan_done=done, plan_total=total
            )

        last = state.get("last") or {}
        last_word = int(last.get("id", 0)) if last.get("kind") == "word" else 0
        if kind == plan_rules.REPEAT:
            pick = await self._uw.pick_active_due(
                user.id, _TRACK, exclude_uw_id=last_word, user_level=user.level
            )
            if pick is None:
                # Nothing is due yet. A mastered word refreshed early is a
                # better use of the slot than a hole in the day.
                pick = await self._uw.pick_review_mastered(
                    user.id, _TRACK, exclude_uw_id=last_word
                )
        elif kind == plan_rules.PHRASE:
            pick = await self._uw.pick_new_phrase(user.id, _TRACK)
        elif kind == plan_rules.NEW_THEME_WORD:
            pick = await self._pick_theme_word(user)
        elif kind == plan_rules.NEW_WORD:
            pick = await self._uw.pick_new_for_push(user.id, _TRACK, user.level)
        else:
            # Every kind the plan can compose is named above. A catch-all here
            # would turn a slot nobody taught this method about into a silent
            # frequency word — the day would look right and teach the wrong
            # thing. Refusing leaves the slot to be ticked off instead.
            log.warning("push_unknown_plan_kind", kind=kind, uid=user.id)
            return False

        if pick is None:
            return False
        uw, word = pick
        ctype = self._card_type(uw, word, user.level)
        msg_id, options, correct = await self._send_card(user, "word", uw.id, card_type=ctype)
        if not msg_id:
            return False
        inflight = self._inflight("word", uw.id, options, correct, now_ts, msg_id, ctype=ctype)
        inflight["plan_kind"] = kind
        state["inflight"] = inflight
        return True

    async def _pick_theme_word(self, user: User):
        """A new word from the theme currently being worked through."""
        theme = await self._uw.current_theme(user.id, _TRACK)
        if theme is None:
            return None
        batch = await self._uw.theme_batch(user.id, _TRACK, theme.id, 1)
        return batch[0] if batch else None

    def _plan_card(self, plan) -> str:
        return plan_rules.render(DayPlanService.counts_by_kind(plan))

    async def _close_day(self, user: User, plan, plan_service: DayPlanService) -> None:
        """Close the plan and say so, exactly once."""
        if not await plan_service.close_if_complete(plan):
            return
        counts = {
            k: sum(
                1 for i in (plan.items or []) if i.get("kind") == k and i.get("done")
            )
            for k in DayPlanService.counts_by_kind(plan)
        }
        topic = await ConstructorRepository(self._session).active_topic(user.id)
        row = (
            await ConstructorRepository(self._session).state(user.id, topic.id)
            if topic is not None
            else None
        )
        await self._session.commit()
        await self._raw_send(
            user.telegram_id,
            day_summary.render(
                counts=counts,
                streak_days=int(user.streak_days or 0),
                topic_title=topic.title if topic else "",
                score_after=float(row.score) if row else None,
            ),
            None,
        )

    async def _tick_plan(self, user: User, kind: str | None) -> None:
        """Mark one slot done after a card settles.

        Called from every settle path rather than inferred later: a card that
        was answered but not ticked leaves the plan short by one forever, and
        the plan would never close.
        """
        if not kind:
            return
        service = DayPlanService(self._session)
        plan = await service._plans.open_plan(user.id, _TRACK)
        if plan is None:
            return
        await service.mark_done(plan, kind)
        await self._session.commit()

    def _inflight(
        self,
        kind: str,
        item_id: int,
        options: list[str],
        correct: str,
        now_ts: float,
        msg_id: int | None = None,
        ctype: str = CARD_RECOGNITION,
    ) -> dict:
        return {
            "kind": kind,
            "id": item_id,
            "uw_id": item_id,  # back-compat for the answer callback validation
            "options": options,
            "correct": correct,
            "msg_id": msg_id,
            "ctype": ctype,
            "attempts": 0,
            "sent_ts": now_ts,
            "retry_ts": now_ts + _retry_after(1),
        }

    async def _send_card(
        self,
        user: User,
        kind: str,
        item_id: int,
        options_override: list[str] | None = None,
        prefix: str = "",
        card_type: str = CARD_RECOGNITION,
        attempt: int = 0,
    ) -> tuple[int | None, list[str] | None, str | None]:
        """Build and send a card (word or grammar). Returns (msg_id, options,
        correct). On a re-push pass options_override so the button order matches
        the stored inflight (otherwise a re-shuffle would break answer checking);
        `card_type` is likewise carried over so the prompt stays stable."""
        built = (
            await self._build_grammar(item_id)
            if kind == "grammar"
            else await self._build_card(
                user.id, item_id, card_type=card_type, user_level=user.level
            )
        )
        if built is None:
            return None, None, None
        text = built[0]
        options = options_override or built[1]
        correct = built[2]
        if prefix:
            text = f"{prefix}\n\n{text}"
        if kind == "grammar":
            kb = push_grammar_card_kb(options, item_id)
        elif card_type in (CARD_CLOZE, CARD_TYPE_IN) and not options:
            # Answered by typing — no answer buttons (options is empty).
            kb = push_cloze_card_kb(item_id, built[3])
        else:
            kb = push_card_kb(options, item_id, built[3])
        msg_id = await self._raw_send(
            user.telegram_id,
            text,
            kb,
            uid=user.id,
            kind=kind,
            obj_id=item_id,
            attempt=attempt,
            # A prefix only ever carries the nudge line, so its presence is what
            # separates "the card arrived again" from "a new card arrived" —
            # the exact question the duplicate-card report could not answer.
            reason="nudge" if prefix else "new",
        )
        return msg_id, options, correct

    # A user cannot receive more than twelve cards an hour by design: the worker
    # ticks every five minutes and sends at most one card per tick. Normal load
    # is far lower — a 28-card plan spread over a twelve-hour window is two or
    # three an hour. Eight sits between the two: high enough that an ordinary
    # busy evening does not trip it, low enough to catch the failure we have
    # actually had. July's bug sent ~40 cards in three and a half hours, about
    # 11 an hour, and was noticed by a human three hours in.
    #
    # A warning, not a block: the July bug was a wiped inflight, and refusing to
    # send would have hidden it rather than fixed it. This makes it findable.
    SEND_RATE_WINDOW_SECONDS = 3600
    SEND_RATE_WARN = 8

    async def _note_send_rate(self, uid: int) -> None:
        """Count sends per user per hour and shout once the count looks wrong.

        Deliberately its own key: it must never touch `push:{uid}`. The July bug
        was one writer clobbering that state with a stale snapshot, and a
        counter that opened it would join the same class of problem.
        """
        if self._redis is None:
            return
        key = f"pushrate:{uid}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self.SEND_RATE_WINDOW_SECONDS)
            elif count == self.SEND_RATE_WARN:
                log.warning("push_rate_high", uid=uid, sent=count, window_s=self.SEND_RATE_WINDOW_SECONDS)
        except Exception:  # noqa: BLE001 — telemetry must never break delivery
            pass

    def _log_idle(self, user: User, state: dict, why: str, **extra) -> None:
        """Say why this tick sent nothing — but only when the answer changes.

        A line per tick would be ~2300 a day for eight users, which is a stream
        nobody reads, and an unread log is the situation this is meant to end.
        Logging transitions keeps it to a handful of lines: "outside_window" at
        dusk, "gap" after an answer, "plan_closed" when the day is done.
        """
        if state.get("idle_why") == why:
            return
        state["idle_why"] = why
        log.info("push_idle", uid=user.id, why=why, **extra)

    async def _raw_send(
        self,
        telegram_id: int,
        text: str,
        reply_markup,
        *,
        uid: int | None = None,
        kind: str = "unknown",
        obj_id: int | None = None,
        attempt: int = 0,
        reason: str = "new",
    ) -> int | None:
        """Send a push card with a prebuilt keyboard; return the new message_id
        (so retries can delete the previous one), or None on failure.

        Every send is logged, one line, because the alternative is what we had:
        a user reported the same card arriving twice five minutes apart and
        there was nothing to check it against — the last log line predated the
        cards by a day. Live Redis state looked healthy, so the report could be
        neither reproduced nor ruled out. `reason` separates a fresh card from
        a nudge, which is exactly the distinction that report turned on.
        """
        if self._bot is None:
            return None
        try:
            msg = await self._bot.send_message(
                telegram_id, text, reply_markup=reply_markup, parse_mode="HTML"
            )
            log.info(
                "push_sent",
                uid=uid,
                kind=kind,
                id=obj_id,
                msg_id=msg.message_id,
                attempt=attempt,
                reason=reason,
            )
            if uid is not None:
                await self._note_send_rate(uid)
            return msg.message_id
        except TelegramForbiddenError:
            # User blocked the bot (or deleted the chat) — bubble up so run_all
            # disables push for them instead of retrying every tick forever.
            raise
        except Exception:  # noqa: BLE001
            log.warning("push_send_failed", tg=telegram_id)
            return None

    async def _build_grammar(self, ugi_id: int) -> tuple[str, list[str], str] | None:
        pair = await self._grammar.item_with_progress(ugi_id)
        if pair is None:
            return None
        ugi, item = pair
        options = [item.correct, *(item.distractors or [])][:4]
        random.shuffle(options)
        text = f"{PUSH_GRAMMAR_CARD.format(prompt=html.escape(item.prompt))}\n<i>{_progress_line(ugi)}</i>"
        return text, options, item.correct

    async def _delete(self, chat_id: int, message_id: int) -> None:
        """Drop a stale push message from chat. If Telegram refuses (too old to
        delete — >48h), at least strip the buttons so the user can't tap a ghost
        card and trigger a stale-callback."""
        if self._bot is None:
            return
        try:
            await self._bot.delete_message(chat_id, message_id)
            return
        except Exception:  # noqa: BLE001 — message may already be gone / too old
            pass
        try:
            await self._bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=None
            )
        except Exception:  # noqa: BLE001 — already stripped / gone
            pass

    def _cloze_possible(self, word: Word) -> bool:
        """Cloze needs an example whose target word can be masked (regular form)."""
        return _mask_target(word.example_sentence or "", word.writing) is not None

    def _card_type(self, uw: UserWord, word: Word, user_level: str | None = None) -> str:
        """Which card type to show, by the word's production-ladder stage.
        New words always start on recognition; mastered words rotate types for
        review variety. The stage boundaries scale with the word's own mastery
        bar (see `levels.ladder_stages`), so a short bar still walks the whole
        ladder instead of promoting the word before it's ever typed."""
        if uw.status == WordStatus.NEW.value:
            return CARD_RECOGNITION
        if uw.status == WordStatus.MASTERED.value:
            choices = [CARD_RECOGNITION, CARD_REVERSE]
            if self._cloze_possible(word):
                choices.append(CARD_CLOZE)
            return random.choice(choices)
        reverse_at, cloze_at = ladder_stages(mastery_reps(word.level, user_level))
        reps = uw.repetitions_count or 0
        if reps < reverse_at:
            return CARD_RECOGNITION
        if reps < cloze_at:
            return CARD_REVERSE
        return CARD_CLOZE if self._cloze_possible(word) else CARD_TYPE_IN

    async def _build_card(
        self,
        user_id: int,
        uw_id: int,
        card_type: str = CARD_RECOGNITION,
        user_level: str | None = None,
    ) -> tuple[str, list[str], str, str] | None:
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return None
        uw, word = pair
        ru = uw.custom_translation or word.translation
        if not ru:
            return None
        target = mastery.target_for(word.level, user_level)
        # Pre-answer surfaces must not leak English inside the RU gloss
        # («не могу (сокращение от cannot)» on a can't card = free answer).
        ru = strip_latin_hints(ru)

        if card_type == CARD_CLOZE:
            masked = _mask_target(word.example_sentence or "", word.writing)
            if masked:
                # Type the missing word into the English sentence (real recall).
                text = (
                    f"{PUSH_CARD_CLOZE.format(translation=html.escape(ru), sentence=html.escape(masked))}"
                    f"\n<i>{_progress_line(uw, target=target, typing_now=True)}</i>"
                )
                # options=[] — answered by typing, not buttons.
                return text, [], word.writing, uw.status
            # Not maskable (irregular form) → fall back to a reverse card.
            card_type = CARD_REVERSE

        if card_type == CARD_TYPE_IN:
            text = (
                f"{PUSH_CARD_TYPE_IN.format(translation=html.escape(ru))}"
                f"\n<i>{_progress_line(uw, target=target, typing_now=True)}</i>"
            )
            # options=[] — answered by typing, like a cloze.
            return text, [], word.writing, uw.status

        if card_type == CARD_REVERSE:
            # RU prompt → pick the English word. Answer is the writing; distractors
            # are other English words. Closes the recognition→production gap.
            distractors = await self._uw.reverse_distractors(
                user_id, track=_TRACK, exclude_word_id=word.id, limit=3,
                correct_pos=word.part_of_speech, correct_level=word.level,
            )
            answer = word.writing
            options = [answer, *distractors[:3]]
            random.shuffle(options)
            text = (
                f"{PUSH_CARD_REVERSE.format(translation=html.escape(ru))}"
                f"\n<i>{_progress_line(uw, target=target)}</i>"
            )
            return text, options, answer, uw.status

        # Recognition (default): EN→RU, pick the translation. Carries the abstract
        # example as a context hint.
        distractors = await self._uw.quiz_distractors(
            user_id, track=_TRACK, exclude_user_word_id=uw_id, limit=3, exclude_translations=[ru],
            correct_pos=word.part_of_speech, correct_level=word.level,
        )
        options = [ru, *distractors[:3]]
        random.shuffle(options)
        text = _format_word_card(
            writing=word.writing,
            abstract_en=word.abstract_example_en,
            abstract_ru=word.abstract_example_ru,
            progress=_progress_line(uw, target=target),
        )
        return text, options, ru, uw.status

    async def show_rule(self, user: User, ugi_id: int, query: CallbackQuery) -> None:
        """Show the rule behind a grammar exercise (the "📖 Правило" button), as a
        separate message tied to the current card so it's cleaned up on answer.
        Sends via the callback's message (handler path has no self._bot)."""
        if query.message is None:
            await query.answer()
            return
        state = await self._load(user.id)
        inflight = state.get("inflight")
        # Stale rule tap: the card is no longer the active inflight (day rolled
        # over, or the user is fishing in old cards). Clean it up instead of
        # opening a rule message for nothing.
        if not inflight or int(inflight.get("id", 0)) != ugi_id or inflight.get("kind") != "grammar":
            try:
                await query.message.delete()
            except Exception:  # noqa: BLE001 — too old / already gone
                try:
                    await query.message.edit_reply_markup(reply_markup=None)
                except Exception:  # noqa: BLE001
                    pass
            await query.answer()
            return
        topic = await self._grammar.topic_for_user_item(ugi_id)
        if topic is None:
            await query.answer()
            return
        bot, chat_id = query.message.bot, query.message.chat.id
        # Don't stack rule messages — drop a previously-opened one first.
        if inflight and inflight.get("rule_msg_id"):
            try:
                await bot.delete_message(chat_id, int(inflight["rule_msg_id"]))
            except Exception:  # noqa: BLE001
                pass
            inflight["rule_msg_id"] = None
        try:
            sent = await query.message.answer(
                PUSH_RULE_CARD.format(title=html.escape(topic.title), rule=topic.rule),
                reply_markup=push_rule_kb(),
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            sent = None
        if sent is not None and inflight is not None:
            inflight["rule_msg_id"] = sent.message_id
            await self._save(user.id, state)
        await query.answer()

    # ---- card controls (handler path): я знаю / перестать показывать / отложить ----

    async def handle_remove(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        """«Убрать из обучения» — out of rotation, no credit, recoverable from
        the archive. Distinct from «Я это знаю», which credits the word: mixing
        the two lost the reason a word left rotation."""
        uw = await self._uw.get(uw_id, owner_id=user.id)  # scope: forged id can't hit another user
        if uw is not None:
            uw.archived = True
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_HIDDEN)

    async def handle_snooze(self, user: User, uw_id: int, days: int, query: CallbackQuery) -> None:
        uw = await self._uw.get(uw_id, owner_id=user.id)  # scope: forged id can't hit another user
        if uw is not None:
            uw.snooze_until = datetime.now(timezone.utc) + timedelta(days=days)
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_SNOOZED.format(label=SNOOZE_LABELS.get(days, f"{days} дн.")))

    async def handle_master(self, user: User, ut: UserTrack, uw_id: int, query: CallbackQuery) -> None:
        """«✅ Уже уверенно знаю» — graduate a word straight to mastered without
        grinding out the remaining reps. For a word the user genuinely knows but
        that sits at a low count because it surfaces rarely (or an old miss
        dropped it). Stays in the light mastered-review rotation."""
        pair = await self._uw.get_with_word(uw_id, owner_id=user.id)  # scope: forged id can't hit another user
        uw, word = pair if pair else (None, None)
        if uw is not None and uw.status != WordStatus.MASTERED.value:
            uw.status = WordStatus.MASTERED.value
            # Park every counter on this word's own bar. Leaving them below it
            # would show a graduated word sitting at "3.0 / 9.5" after an
            # unarchive, as if it had regressed.
            target_score, needed_production = mastery.target_for(word.level, user.level)
            uw.learning_score = target_score
            uw.production_count = max(uw.production_count or 0, needed_production)
            uw.repetitions_count = mastery_reps(word.level, user.level)
            uw.mastery_score = 5.0
            uw.next_review_at = datetime.now(timezone.utc) + timedelta(days=7)
            await self._session.flush()
            await ProgressService(self._session).update_streak(user)
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_MASTERED_KNOWN)

    async def _advance_after_card(self, user_id: int, uw_id: int) -> None:
        """Drop the current WORD card and let the next one come on the next tick.
        Only clears a word inflight of the same id — a hide/snooze (word-only
        action) must never clear a grammar card that happens to share the id
        (word and grammar ids are independent sequences)."""
        state = await self._load(user_id)
        inflight = state.get("inflight")
        if (
            inflight
            and inflight.get("kind", "word") == "word"
            and int(inflight.get("uw_id", 0)) == uw_id
        ):
            state["inflight"] = None
        state["next_ts"] = datetime.now(timezone.utc).timestamp()
        await self._save(user_id, state)

    async def _finish_card(self, query: CallbackQuery, text: str) -> None:
        if query.message:
            try:
                await query.message.edit_text(text)
            except Exception:  # noqa: BLE001
                pass
        await query.answer(text)

    # ---- answer (handler path) ----

    async def handle_answer(
        self, user: User, ut: UserTrack, uw_id: int, idx: int, query: CallbackQuery
    ) -> None:
        state = await self._load(user.id)
        inflight = state.get("inflight")
        iid = int(inflight.get("id", inflight.get("uw_id", 0))) if inflight else 0
        tapped_msg = query.message.message_id if query.message else 0
        # The tapped card must be the CURRENT inflight: same item id AND same
        # message. The message check matters because word and grammar ids come
        # from independent sequences and both pack into PushCB.uw_id — a ghost
        # word card whose id collides with the live grammar card would otherwise
        # be graded against the wrong exercise.
        if not inflight or iid != uw_id or tapped_msg != int(inflight.get("msg_id") or 0):
            # Tapped on an old card whose inflight is gone. Don't just toast —
            # remove the ghost from chat so it stops accumulating.
            if query.message is not None:
                try:
                    await query.message.delete()
                except Exception:  # noqa: BLE001 — too old / already gone
                    try:
                        await query.message.edit_reply_markup(reply_markup=None)
                    except Exception:  # noqa: BLE001
                        pass
            await query.answer(PUSH_STALE, show_alert=False)
            return
        options = inflight.get("options") or []
        if idx < 0 or idx >= len(options):
            await query.answer()
            return
        # Claim the answer atomically — a double-tap must not apply SR twice.
        if not await self._claim_answer(user.id, tapped_msg):
            await query.answer()
            return
        correct = options[idx] == inflight.get("correct")
        correct_answer_text = str(inflight.get("correct") or "")
        rule_msg_id = inflight.get("rule_msg_id")

        now_ts = datetime.now(timezone.utc).timestamp()
        response_ms, attempts = _timing(inflight, now_ts)
        await self._tick_plan(user, inflight.get("plan_kind"))

        leech_writing: str | None = None
        recap = ""  # grammar cards have no word to recap
        if inflight.get("kind") == "grammar":
            await self._apply_grammar_answer(
                user, ut, iid, correct, response_ms=response_ms, attempts=attempts
            )
        else:
            outcome = await self._apply_word_answer(
                user, ut, iid, correct, card_type=inflight.get("ctype"),
                response_ms=response_ms, attempts=attempts,
            )
            leech_writing, recap = outcome.leech_writing, outcome.recap

        state["inflight"] = None
        # Remember this card so the next pick skips it (no back-to-back repeats).
        state["last"] = {"kind": inflight.get("kind", "word"), "id": iid}
        state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
        await self._save(user.id, state)

        # Clean up the rule message the user may have opened for this card
        # (handler path has no self._bot, so use the callback's message bot).
        if rule_msg_id and query.message is not None:
            try:
                await query.message.bot.delete_message(query.message.chat.id, int(rule_msg_id))
            except Exception:  # noqa: BLE001
                pass

        feedback = (
            PUSH_ANSWER_CORRECT
            if correct
            else PUSH_ANSWER_WRONG.format(answer=html.escape(correct_answer_text))
        ) + recap
        if query.message:
            try:
                await query.message.edit_text(feedback, parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        await query.answer("✅" if correct else "❌")

        # This word has been missed LEECH_THRESHOLD times in a row — offer to
        # postpone it so it stops blocking a slot. A separate message with its
        # own buttons (the card itself is already edited to feedback).
        if leech_writing and query.message is not None:
            try:
                await query.message.answer(
                    PUSH_LEECH_PROMPT.format(word=html.escape(leech_writing)),
                    reply_markup=push_leech_kb(iid),
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _typed_feedback(correct: bool, answer: str, verdict) -> str:
        """What the card says after a typed answer.

        Three cases, deliberately distinct: understood and forgiven, understood
        and refused (with the reason), and couldn't check — the last one says so
        rather than letting the bot look like it stopped understanding.
        """
        safe = html.escape(answer)
        if correct and verdict is not None and verdict.hint:
            return PUSH_ANSWER_ALMOST.format(answer=safe, hint=html.escape(verdict.hint))
        if correct:
            return PUSH_ANSWER_CORRECT
        if verdict is None:
            return PUSH_ANSWER_DEGRADED.format(answer=safe)
        if verdict.hint:
            return PUSH_ANSWER_WRONG_HINT.format(answer=safe, hint=html.escape(verdict.hint))
        return PUSH_ANSWER_WRONG.format(answer=safe)

    async def _settle_cloze(
        self,
        user: User,
        ut: UserTrack,
        iid: int,
        correct: bool,
        state: dict,
        inflight: dict,
        verdict=None,
        answered_ts: float | None = None,
    ) -> AnswerOutcome:
        """Apply a typed answer's SR result and advance the push state.

        `answered_ts` is when the user's answer actually arrived. It matters on
        the typed path: a miss goes to the AI checker first, and timing from
        after that call would bill the model's latency to the learner.
        """
        now_ts = datetime.now(timezone.utc).timestamp()
        response_ms, attempts = _timing(inflight, answered_ts if answered_ts else now_ts)
        await self._tick_plan(user, inflight.get("plan_kind"))
        outcome = await self._apply_word_answer(
            user, ut, iid, correct,
            card_type=inflight.get("ctype") or CARD_CLOZE,
            kind_override=verdict.kind if verdict is not None else None,
            response_ms=response_ms, attempts=attempts,
        )
        state["inflight"] = None
        state["last"] = {"kind": "word", "id": iid}
        state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
        await self._save(user.id, state)
        return outcome

    async def handle_typed_answer(self, user: User, ut: UserTrack, message) -> bool:
        """A free-text message while a cloze card is in flight = the typed answer.
        Returns True if it consumed the message (so the caller skips quick-add)."""
        state = await self._load(user.id)
        inflight = state.get("inflight")
        if not inflight or inflight.get("kind") != "word":
            return False
        ctype = inflight.get("ctype")
        if ctype not in _TYPED_CARDS:
            return False
        # Only consume text that looks like an answer to THIS card — otherwise a
        # normal quick-add ("serendipity - прозорливость") gets eaten as a wrong
        # answer and silently deleted while a stale card sits in the chat.
        if not _looks_like_typed_answer(message.text or "", ctype):
            return False
        # Claim atomically so a typed answer racing the «🤷 Не помню» tap can't
        # both settle the same card.
        if not await self._claim_answer(user.id, inflight.get("msg_id")):
            return True  # already settled by the other path; just swallow the text
        # Stamped before the checker runs, so a miss isn't charged its latency.
        answered_ts = datetime.now(timezone.utc).timestamp()
        iid = int(inflight.get("id", inflight.get("uw_id", 0)))
        answer = str(inflight.get("correct") or "")
        typed = message.text or ""
        correct = is_typing_correct(typed, answer)

        # Only consult the checker when the strict rule already said no: a
        # correct answer stays instant and costs nothing.
        verdict = None
        if not correct:
            # One extra read, and only on a miss: the checker needs the meaning
            # to tell a valid synonym from a different word.
            pair = await self._uw.get_with_word(iid)
            translation = ""
            if pair is not None:
                uw_row, word_row = pair
                translation = uw_row.custom_translation or word_row.translation or ""
            verdict = await self._checker.classify(answer, translation, typed)
            if verdict is None:
                # Scored strictly because the checker was unreachable. Park it so
                # the credit is delayed, not lost.
                await self._regrade.park(
                    ParkedAnswer(
                        user_id=user.id,
                        telegram_id=user.telegram_id,
                        user_word_id=iid,
                        word=answer,
                        translation=translation,
                        answer=typed,
                        at=datetime.now(timezone.utc).timestamp(),
                    )
                )
            elif verdict.credited:
                correct = True

        outcome = await self._settle_cloze(
            user, ut, iid, correct, state, inflight, verdict=verdict,
            answered_ts=answered_ts,
        )
        leech = outcome.leech_writing
        feedback = self._typed_feedback(correct, answer, verdict) + outcome.recap
        msg_id = inflight.get("msg_id")
        if msg_id:
            try:
                await message.bot.edit_message_text(
                    feedback, chat_id=message.chat.id, message_id=int(msg_id), parse_mode="HTML"
                )
            except Exception:  # noqa: BLE001
                pass
        # Tidy the user's typed answer out of the chat.
        try:
            await message.delete()
        except Exception:  # noqa: BLE001
            pass
        if leech:
            try:
                await message.answer(
                    PUSH_LEECH_PROMPT.format(word=html.escape(leech)),
                    reply_markup=push_leech_kb(iid),
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass
        return True

    async def handle_giveup(self, user: User, ut: UserTrack, uw_id: int, query: CallbackQuery) -> None:
        """The "🤷 Не помню" button on a cloze card — count it wrong and reveal."""
        state = await self._load(user.id)
        inflight = state.get("inflight")
        iid = int(inflight.get("id", inflight.get("uw_id", 0))) if inflight else 0
        if not inflight or iid != uw_id or inflight.get("ctype") != CARD_CLOZE:
            await query.answer(PUSH_STALE, show_alert=False)
            return
        # Claim atomically — give-up racing a typed answer must settle once.
        if not await self._claim_answer(user.id, inflight.get("msg_id")):
            await query.answer()
            return
        answer = str(inflight.get("correct") or "")
        outcome = await self._settle_cloze(user, ut, iid, False, state, inflight)
        leech = outcome.leech_writing
        if query.message:
            try:
                await query.message.edit_text(
                    PUSH_ANSWER_WRONG.format(answer=html.escape(answer)) + outcome.recap,
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass
        await query.answer("💡")
        if leech and query.message is not None:
            try:
                await query.message.answer(
                    PUSH_LEECH_PROMPT.format(word=html.escape(leech)),
                    reply_markup=push_leech_kb(iid),
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass

    async def handle_leech_park(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        """Postpone a stuck word: snooze it for LEECH_PARK_DAYS (out of rotation,
        frees its slot, auto-returns) and clear the miss streak."""
        uw = await self._uw.get(uw_id)
        if uw is not None and uw.user_id == user.id:
            uw.snooze_until = datetime.now(timezone.utc) + timedelta(days=LEECH_PARK_DAYS)
            uw.consecutive_wrong = 0
            await self._session.flush()
        await self._finish_card(query, PUSH_LEECH_PARKED)

    async def handle_leech_keep(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        """Keep drilling a stuck word — just reset the miss streak so we don't
        nag again on the very next miss."""
        uw = await self._uw.get(uw_id)
        if uw is not None and uw.user_id == user.id:
            uw.consecutive_wrong = 0
            await self._session.flush()
        await self._finish_card(query, PUSH_LEECH_KEPT)

    async def _record(self, user, uw, word, kind: str, card_type: str | None, was_mastered: bool) -> None:
        """Log what this answer proved, and whether it finished the word.

        The tables show where every word stands; these show movement — which is
        the only way to answer "did the rework help", a question that has been
        unanswerable since the rework landed.
        """
        await self._analytics.emit(
            EVENT_ANSWER_GRADED,
            user_id=user.id,
            kind=kind,
            card=card_type or CARD_RECOGNITION,
            word_level=word.level,
            user_level=user.level,
        )
        if not was_mastered and uw.status == WordStatus.MASTERED.value:
            await self._analytics.emit(
                EVENT_WORD_MASTERED,
                user_id=user.id,
                word_level=word.level,
                user_level=user.level,
                typed=uw.production_count or 0,
                mistakes=uw.mistakes_count or 0,
            )

    async def _apply_word_answer(
        self,
        user: User,
        ut: UserTrack,
        uw_id: int,
        correct: bool,
        card_type: str | None = None,
        kind_override: str | None = None,
        response_ms: int | None = None,
        attempts: int | None = None,
    ) -> AnswerOutcome:
        """Apply the SR result and leech tracking.

        Returns the leech writing (set only when this wrong answer just crossed
        the threshold, so the caller can offer to postpone the word) together
        with the recap block for the reveal — built here because this is the
        only place holding the word both before and after the review.
        """
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return AnswerOutcome()
        uw, word = pair
        was_mastered = uw.status == WordStatus.MASTERED.value
        target = mastery.target_for(word.level, user.level)
        before_percent = _percent(uw, target)
        kind = kind_override or _answer_kind(card_type, correct)
        apply_review(
            uw,
            ReviewResult.CORRECT if correct else ReviewResult.WRONG,
            LearningPace(ut.learning_pace),
            kind=kind,
            word_level=word.level,
            user_level=user.level,
            # Every word with a translation can be typed now: a cloze where a
            # sentence allows it, the whole thing written out where it doesn't.
            production_possible=bool(uw.custom_translation or word.translation),
        )
        await self._record(user, uw, word, kind, card_type, was_mastered)

        # Leech tracking: count consecutive misses on words still being learned.
        uw.consecutive_wrong, is_leech = _leech_after(uw.consecutive_wrong, correct, was_mastered)
        leech_writing = word.writing if is_leech else None

        await self._reviews.create(
            user_id=user.id, track=_TRACK, user_word_id=uw_id,
            session_id=None, result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
            response_ms=response_ms, attempts=attempts,
        )
        await self._session.flush()
        await ProgressService(self._session).update_streak(user)
        # A word just got mastered → a course slot freed up; top the pipeline back up.
        if not was_mastered and uw.status == WordStatus.MASTERED.value:
            from app.services.course_service import CourseService

            await CourseService(self._session, self._redis).refill(user, ut, _TRACK)
        return AnswerOutcome(
            leech_writing=leech_writing,
            recap=_recap(
                uw, word,
                before_percent=before_percent,
                was_mastered=was_mastered,
                correct=correct,
                target=target,
            ),
        )

    async def _apply_grammar_answer(
        self,
        user: User,
        ut: UserTrack,
        ugi_id: int,
        correct: bool,
        response_ms: int | None = None,
        attempts: int | None = None,
    ) -> None:
        ugi = await self._grammar.get_user_item(ugi_id)
        if ugi is None:
            return
        was_mastered = ugi.status == WordStatus.MASTERED.value
        apply_review(ugi, ReviewResult.CORRECT if correct else ReviewResult.WRONG, LearningPace(ut.learning_pace))
        await self._grammar_reviews.create(
            user_id=user.id, track=_TRACK, user_grammar_item_id=ugi_id,
            result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
            response_ms=response_ms, attempts=attempts,
        )
        await self._session.flush()
        await ProgressService(self._session).update_streak(user)
        # Grammar item mastered → advance the course (next topic + word top-up).
        if not was_mastered and ugi.status == WordStatus.MASTERED.value:
            from app.services.course_service import CourseService

            await CourseService(self._session, self._redis).refill(user, ut, _TRACK)

    # ---- batch triage ------------------------------------------------------
    #
    # One screen per theme instead of the same judgement forty times across six
    # weeks. Marked words graduate rather than disappear — the same outcome as
    # «уже уверенно знаю» on a card — so they stay in the occasional refresh.
    # Claiming to know a word is not proof, and being asked about it in a month
    # is the cheapest way to find out otherwise.

    async def _send_triage(self, user: User, state: dict, now_ts: float) -> bool:
        """Offer the next screenful of the current theme. False if there is
        nothing to offer — the caller ticks the slot rather than holding the
        day open for a screen that will never come.

        Writes into the caller's `state`; see `_send_constructor` for why
        loading a private copy here silently wipes the card."""
        if state.get("triage_skip_day") == state.get("day"):
            # Already offered and ignored today — see the abandon branch.
            return False
        theme = await self._uw.current_theme(user.id, _TRACK)
        if theme is None:
            return False
        batch = await self._uw.theme_batch(user.id, _TRACK, theme.id, triage.BATCH_SIZE)
        if not batch:
            return False

        state = triage.TriageState()
        rows = [
            (uw.id, triage.button_label(word.writing, word.translation or "", False))
            for uw, word in batch
        ]
        msg_id = await self._raw_send(
            user.telegram_id,
            triage.render(theme.title, offered=len(rows), known=0),
            triage_kb(rows, TRIAGE_DONE),
        )
        if msg_id is None:
            return False

        state["inflight"] = {
            "kind": "triage",
            "id": theme.id,
            "title": theme.title,
            "rows": [[uw.id, word.writing, word.translation or ""] for uw, word in batch],
            "state": state.to_dict(),
            "msg_id": msg_id,
            "attempts": 0,
            "sent_ts": now_ts,
            "retry_ts": now_ts + _retry_after(1),
        }
        return True

    async def _triage_context(self, user: User, query: CallbackQuery):
        push_state = await self._load(user.id)
        inflight = push_state.get("inflight") or {}
        tapped = query.message.message_id if query.message else 0
        if inflight.get("kind") != "triage" or tapped != int(inflight.get("msg_id") or 0):
            await query.answer(PUSH_STALE, show_alert=False)
            return None
        return push_state, inflight, triage.TriageState.from_dict(inflight.get("state"))

    async def handle_triage_toggle(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        ctx = await self._triage_context(user, query)
        if ctx is None:
            return
        push_state, inflight, state = ctx
        rows = inflight.get("rows") or []
        # Only ids from this screen: a forged callback must not graduate a word
        # the learner was never shown.
        if not any(int(r[0]) == uw_id for r in rows):
            await query.answer()
            return

        state = state.toggle(uw_id)
        inflight["state"] = state.to_dict()
        push_state["inflight"] = inflight
        await self._save(user.id, push_state)

        labelled = [
            (int(r[0]), triage.button_label(r[1], r[2], state.marked(int(r[0])))) for r in rows
        ]
        try:
            await query.message.edit_text(
                triage.render(
                    str(inflight.get("title") or ""),
                    offered=len(rows),
                    known=len(state.known),
                ),
                parse_mode="HTML",
                reply_markup=triage_kb(labelled, TRIAGE_DONE),
            )
        except Exception:  # noqa: BLE001 — card gone or text unchanged
            pass
        await query.answer()

    async def handle_triage_done(self, user: User, ut: UserTrack, query: CallbackQuery) -> None:
        ctx = await self._triage_context(user, query)
        if ctx is None:
            return
        push_state, inflight, state = ctx
        rows = inflight.get("rows") or []
        offered = {int(r[0]) for r in rows}

        for uw_id in state.known:
            if int(uw_id) in offered:
                await self._graduate_known(user, int(uw_id))
        await self._session.commit()

        try:
            await query.message.edit_text(
                triage.render_summary(
                    str(inflight.get("title") or ""),
                    known=len(state.known),
                    learning=len(offered) - len(state.known),
                ),
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass

        now_ts = datetime.now(timezone.utc).timestamp()
        await self._tick_plan(user, plan_rules.TRIAGE)
        push_state["inflight"] = None
        push_state["next_ts"] = now_ts + _minutes(
            self._s.push_gap_min_minutes, self._s.push_gap_max_minutes
        )
        await self._save(user.id, push_state)
        await query.answer()

    async def _graduate_known(self, user: User, uw_id: int) -> None:
        """Mark one word as already known — the same outcome as the per-card
        «уже уверенно знаю», so the two routes cannot drift into meaning
        different things."""
        pair = await self._uw.get_with_word(uw_id, owner_id=user.id)
        if pair is None:
            return
        uw, word = pair
        if uw.status == WordStatus.MASTERED.value:
            return
        uw.status = WordStatus.MASTERED.value
        target_score, needed_production = mastery.target_for(word.level, user.level)
        uw.learning_score = target_score
        uw.production_count = max(uw.production_count or 0, needed_production)
        uw.mastery_score = 5.0
        uw.next_review_at = datetime.now(timezone.utc) + timedelta(days=7)
        await self._session.flush()

    # ---- topic check -------------------------------------------------------
    #
    # Ten sentences in a row, one attempt each, no hints. The only place a
    # session format is used, because "in a row, unaided" is the property being
    # measured — spreading these across a day restores the context the check
    # exists to remove.
    #
    # One message for the whole thing: the offer becomes question one, each
    # answer replaces it with the next, and the last becomes the report.

    async def _send_test(self, user: User, state: dict, now_ts: float) -> bool:
        """Offer a due check. False when none is due.

        Writes into the caller's `state`; see `_send_constructor`."""
        repo = ConstructorRepository(self._session)
        topic = await repo.due_test_topic(user.id)
        if topic is None:
            return False
        row = await repo.state(user.id, topic.id)
        phrases = await repo.test_phrases(
            topic.id, topic_test.TEST_SIZE, exclude=[int(i) for i in (row.recent if row else []) or []]
        )
        if not phrases:
            return False

        msg_id = await self._raw_send(
            user.telegram_id,
            topic_test.render_offer(topic.title),
            test_offer_kb(topic.id),
        )
        if msg_id is None:
            return False
        state["inflight"] = {
            "kind": "test",
            "id": topic.id,
            "title": topic.title,
            "phrases": [p.id for p in phrases],
            "idx": 0,
            "started": False,
            "results": [],
            "msg_id": msg_id,
            "attempts": 0,
            "sent_ts": now_ts,
            "retry_ts": now_ts + _retry_after(1),
        }
        return True

    async def _test_context(self, user: User, topic_id: int, query: CallbackQuery):
        push_state = await self._load(user.id)
        inflight = push_state.get("inflight") or {}
        tapped = query.message.message_id if query.message else 0
        if (
            inflight.get("kind") != "test"
            or int(inflight.get("id", 0)) != topic_id
            or tapped != int(inflight.get("msg_id") or 0)
        ):
            await query.answer(PUSH_STALE, show_alert=False)
            return None
        return push_state, inflight

    async def handle_test_start(self, user: User, topic_id: int, query: CallbackQuery) -> None:
        ctx = await self._test_context(user, topic_id, query)
        if ctx is None:
            return
        push_state, inflight = ctx
        inflight["started"] = True
        push_state["inflight"] = inflight
        await self._save(user.id, push_state)
        await self._show_test_question(user, inflight, query.message)
        await query.answer()

    async def handle_test_later(self, user: User, topic_id: int, query: CallbackQuery) -> None:
        """Defer without penalty. A check that starts the moment it arrives is
        a trap when it lands mid-commute, and a trap gets ignored rather than
        deferred — which costs the measurement entirely."""
        ctx = await self._test_context(user, topic_id, query)
        if ctx is None:
            return
        push_state, inflight = ctx
        repo = ConstructorRepository(self._session)
        row = await repo.ensure_state(user.id, topic_id)
        row.test_due_at = datetime.now(timezone.utc) + timedelta(days=1)
        await self._session.commit()

        try:
            await query.message.edit_text(
                f"📝 <b>{html.escape(str(inflight.get('title') or ''))}</b> — проверим завтра.",
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass
        now_ts = datetime.now(timezone.utc).timestamp()
        push_state["inflight"] = None
        push_state["next_ts"] = now_ts + _minutes(
            self._s.push_gap_min_minutes, self._s.push_gap_max_minutes
        )
        await self._save(user.id, push_state)
        await query.answer()

    async def _show_test_question(self, user: User, inflight: dict, message) -> None:
        repo = ConstructorRepository(self._session)
        idx = int(inflight.get("idx", 0))
        phrase_ids = inflight.get("phrases") or []
        phrase = await repo.get_phrase(int(phrase_ids[idx]))
        if phrase is None:
            return
        correct = sum(1 for r in (inflight.get("results") or []) if r.get("ok"))
        try:
            await message.edit_text(
                topic_test.render_question(
                    str(inflight.get("title") or ""), phrase.ru, idx, correct
                ),
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass

    async def handle_test_typed(self, user: User, message) -> bool:
        """A typed message while a check is running."""
        push_state = await self._load(user.id)
        inflight = push_state.get("inflight") or {}
        if inflight.get("kind") != "test" or not inflight.get("started"):
            return False

        repo = ConstructorRepository(self._session)
        idx = int(inflight.get("idx", 0))
        phrase_ids = inflight.get("phrases") or []
        if idx >= len(phrase_ids):
            return True
        phrase = await repo.get_phrase(int(phrase_ids[idx]))
        if phrase is None:
            return True

        typed = message.text or ""
        ok = ctor.matches(typed, phrase.en, list(phrase.alternatives or []))
        results = list(inflight.get("results") or [])
        results.append({"id": phrase.id, "ok": ok, "given": typed, "ru": phrase.ru, "en": phrase.en})
        inflight["results"] = results
        inflight["idx"] = idx + 1
        push_state["inflight"] = inflight
        await self._save(user.id, push_state)

        try:
            await message.delete()
        except Exception:  # noqa: BLE001
            pass

        target = _EditTarget(message.bot, message.chat.id, int(inflight.get("msg_id") or 0))
        if inflight["idx"] < len(phrase_ids):
            await self._show_test_question(user, inflight, target)
            return True
        await self._finish_test(user, push_state, inflight, target)
        return True

    async def _finish_test(self, user: User, push_state: dict, inflight: dict, message) -> None:
        results = inflight.get("results") or []
        correct = sum(1 for r in results if r.get("ok"))
        held = topic_test.passed(correct)
        topic_id = int(inflight.get("id", 0))

        repo = ConstructorRepository(self._session)
        row = await repo.state(user.id, topic_id)
        streak = int(row.held_streak or 0) if row else 0
        next_days = topic_test.next_interval_days(streak + 1 if held else 0)
        await repo.record_test(user.id, topic_id, correct, held, next_days)
        await self._session.commit()

        mistakes = [
            (r.get("ru", ""), r.get("given", ""), r.get("en", ""))
            for r in results
            if not r.get("ok")
        ]
        try:
            await message.edit_text(
                topic_test.render_result(
                    str(inflight.get("title") or ""), correct, mistakes, next_days
                ),
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass

        now_ts = datetime.now(timezone.utc).timestamp()
        await self._tick_plan(user, plan_rules.TEST)
        push_state["inflight"] = None
        push_state["next_ts"] = now_ts + _minutes(
            self._s.push_gap_min_minutes, self._s.push_gap_max_minutes
        )
        await self._save(user.id, push_state)

    # ---- sentence constructor --------------------------------------------
    #
    # A constructor card is one message for its whole life. It is sent once —
    # that is the notification — and every tap edits it in place. The pieces
    # the learner has chosen live in the inflight blob beside the rest of the
    # push state; nothing else is persisted until the card settles.
    #
    # Note the two unrelated meanings of "attempt" on this path. The inflight's
    # `attempts` counts how many times the bot re-pushed an ignored card, and
    # `state.attempt` counts the learner's tries at the sentence. They are kept
    # in separate places on purpose: conflating them would let a nudge look
    # like a wrong answer.

    async def _send_constructor(
        self, user: User, state: dict, now_ts: float, plan_done: int = 0, plan_total: int = 0
    ) -> bool:
        """Open a construction card. False when there is nothing to serve.

        Writes the inflight into the caller's `state` rather than loading its
        own copy. Loading one here means the caller's save — which happens
        after this returns — writes a snapshot taken before the card existed,
        wiping the inflight the moment it is created. The next tick then finds
        no card in flight and sends another, every tick, forever.
        """
        opened = await ConstructorService(self._session).open_card(
            user.id, plan_done=plan_done, plan_total=plan_total
        )
        if opened is None:
            return False
        view, phrase, topic = opened
        kb = (
            constructor_typing_kb(view.phrase_id)
            if view.typing
            else constructor_slots_kb(view.options, view.phrase_id, view.can_undo)
        )
        msg_id = await self._raw_send(
            user.telegram_id, view.text, kb, uid=user.id, kind="constructor", obj_id=view.phrase_id
        )
        if msg_id is None:
            return False

        state["inflight"] = {
            "kind": "phrase",
            "id": view.phrase_id,
            "topic_id": topic.id,
            "state": ctor.CardState(typing=view.typing).to_dict(),
            "msg_id": msg_id,
            "attempts": 0,
            "sent_ts": now_ts,
            "retry_ts": now_ts + _retry_after(1),
        }
        return True

    async def _constructor_context(self, user: User, phrase_id: int, query: CallbackQuery):
        """Validate a tap and load what it needs, or None if the card is stale.

        The message id has to match as well as the phrase id: a ghost card from
        an earlier day carries a real phrase id, and grading a tap against the
        live card's state would apply it to a sentence the learner is not
        looking at.
        """
        state = await self._load(user.id)
        inflight = state.get("inflight") or {}
        tapped = query.message.message_id if query.message else 0
        if (
            inflight.get("kind") != "phrase"
            or int(inflight.get("id", 0)) != phrase_id
            or tapped != int(inflight.get("msg_id") or 0)
        ):
            await query.answer(PUSH_STALE, show_alert=False)
            return None
        repo = ConstructorRepository(self._session)
        phrase = await repo.get_phrase(phrase_id)
        topic = await self._session.get(GrammarTopic, int(inflight.get("topic_id", 0)))
        if phrase is None or topic is None:
            await query.answer(PUSH_STALE, show_alert=False)
            return None
        return state, inflight, phrase, topic, ctor.CardState.from_dict(inflight.get("state"))

    async def _edit_constructor(self, query: CallbackQuery, view) -> None:
        kb = (
            constructor_typing_kb(view.phrase_id)
            if view.typing
            else constructor_slots_kb(view.options, view.phrase_id, view.can_undo)
        )
        try:
            await query.message.edit_text(view.text, parse_mode="HTML", reply_markup=kb)
        except Exception:  # noqa: BLE001 — unchanged text, or the card is gone
            pass

    async def _store_card_state(self, user: User, state: dict, inflight: dict, card: ctor.CardState) -> None:
        inflight["state"] = card.to_dict()
        state["inflight"] = inflight
        await self._save(user.id, state)

    async def _settle_constructor(
        self,
        user: User,
        state: dict,
        inflight: dict,
        phrase,
        topic,
        card: ctor.CardState,
        answer: str | None,
        message,
    ) -> None:
        """Grade the finished sentence, show it, and free the card."""
        result = await ConstructorService(self._session).settle(
            user.id, phrase, topic, card, answer=answer
        )
        await self._session.commit()

        text = ctor.render_result(
            ru=phrase.ru,
            en=result.expected,
            correct=result.correct,
            answer_credit=result.answer_credit,
        )
        if result.switched_to_typing:
            text += "\n\n<i>Дальше без подсказок — пишешь сам.</i>"
        if result.passed:
            text += f"\n\n🎓 <b>{html.escape(topic.title)}</b> — тема сдана."
        try:
            await message.edit_text(text, parse_mode="HTML")
        except Exception:  # noqa: BLE001
            pass

        now_ts = datetime.now(timezone.utc).timestamp()
        await self._tick_plan(user, plan_rules.GRAMMAR)
        state["inflight"] = None
        state["last"] = {"kind": "phrase", "id": phrase.id}
        state["next_ts"] = now_ts + _minutes(
            self._s.push_gap_min_minutes, self._s.push_gap_max_minutes
        )
        await self._save(user.id, state)

    async def handle_slot(self, user: User, phrase_id: int, idx: int, query: CallbackQuery) -> None:
        ctx = await self._constructor_context(user, phrase_id, query)
        if ctx is None:
            return
        state, inflight, phrase, topic, card = ctx
        if not await self._claim_answer(user.id, inflight.get("msg_id")):
            await query.answer()
            return

        service = ConstructorService(self._session)
        card, view = await service.tap_slot(user.id, phrase, topic, card, idx)
        if view is not None:
            await self._store_card_state(user, state, inflight, card)
            await self._edit_constructor(query, view)
            await query.answer()
            return
        await self._settle_constructor(
            user, state, inflight, phrase, topic, card, None, query.message
        )
        await query.answer()

    async def handle_constructor_undo(self, user: User, phrase_id: int, query: CallbackQuery) -> None:
        ctx = await self._constructor_context(user, phrase_id, query)
        if ctx is None:
            return
        state, inflight, phrase, topic, card = ctx
        card, view = await ConstructorService(self._session).undo(user.id, phrase, topic, card)
        await self._store_card_state(user, state, inflight, card)
        await self._edit_constructor(query, view)
        await query.answer()

    async def handle_constructor_hint(self, user: User, phrase_id: int, query: CallbackQuery) -> None:
        ctx = await self._constructor_context(user, phrase_id, query)
        if ctx is None:
            return
        state, inflight, phrase, topic, card = ctx
        service = ConstructorService(self._session)
        card, view = await service.hint(user.id, phrase, topic, card)
        # A hint on the last slot finishes the sentence, so the card has to
        # settle rather than re-render with nothing left to tap.
        if ctor.is_complete(list(phrase.slots or []), list(card.chosen)):
            await self._settle_constructor(
                user, state, inflight, phrase, topic, card, None, query.message
            )
            await query.answer()
            return
        await self._store_card_state(user, state, inflight, card)
        await self._edit_constructor(query, view)
        await query.answer()

    async def handle_constructor_giveup(self, user: User, phrase_id: int, query: CallbackQuery) -> None:
        ctx = await self._constructor_context(user, phrase_id, query)
        if ctx is None:
            return
        state, inflight, phrase, topic, card = ctx
        if not await self._claim_answer(user.id, inflight.get("msg_id")):
            await query.answer()
            return
        # Spend every attempt: giving up is not a near miss, and scoring it as
        # one would make «не помню» the cheapest way through a hard sentence.
        card = replace(card, attempt=ctor.MAX_ATTEMPTS + 1)
        await self._settle_constructor(
            user, state, inflight, phrase, topic, card, "", query.message
        )
        await query.answer()

    async def handle_constructor_typed(self, user: User, message) -> bool:
        """A free-text message while a constructor card is in flight.

        Returns True when it consumed the message, so the caller does not treat
        the sentence as a word to quick-add.
        """
        state = await self._load(user.id)
        inflight = state.get("inflight") or {}
        if inflight.get("kind") != "phrase":
            return False
        card = ctor.CardState.from_dict(inflight.get("state"))
        if not card.typing:
            return False
        if not await self._claim_answer(user.id, inflight.get("msg_id")):
            return True

        repo = ConstructorRepository(self._session)
        phrase = await repo.get_phrase(int(inflight.get("id", 0)))
        topic = await self._session.get(GrammarTopic, int(inflight.get("topic_id", 0)))
        if phrase is None or topic is None:
            return True

        typed = message.text or ""
        correct = ctor.matches(typed, phrase.en, list(phrase.alternatives or []))
        # The learner's own message is removed either way: the card carries the
        # verdict, and leaving the attempt behind turns the chat into a log of
        # half-remembered sentences.
        try:
            await message.delete()
        except Exception:  # noqa: BLE001
            pass

        bot_message = _EditTarget(message.bot, message.chat.id, int(inflight.get("msg_id") or 0))
        if correct or card.attempt >= ctor.MAX_ATTEMPTS:
            await self._settle_constructor(
                user, state, inflight, phrase, topic, card, typed, bot_message
            )
            return True

        card = ctor.miss(card)
        await self._store_card_state(user, state, inflight, card)
        view = await ConstructorService(self._session)._rerender(
            user.id, topic, phrase, card, 0, 0
        )
        try:
            await bot_message.edit_text(
                view.text, parse_mode="HTML", reply_markup=constructor_typing_kb(phrase.id)
            )
        except Exception:  # noqa: BLE001
            pass
        return True


class _EditTarget:
    """Adapts a raw (bot, chat, message) triple to the `.edit_text` interface
    the settle path expects, so typed answers and taps share one code path
    instead of each growing its own copy of the finishing logic."""

    def __init__(self, bot, chat_id: int, message_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._message_id = message_id

    async def edit_text(self, text: str, **kwargs):
        return await self._bot.edit_message_text(
            text=text, chat_id=self._chat_id, message_id=self._message_id, **kwargs
        )
