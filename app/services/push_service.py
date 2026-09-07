from __future__ import annotations

import html
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.push import (
    SNOOZE_LABELS,
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
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult, WordStatus
from app.domain import mastery
from app.domain.levels import ladder_stages, mastery_reps
from app.domain.study_drill import is_typing_correct
from app.domain.models import User, UserTrack
from app.domain.pacing import pace_of, pool_ceiling
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


# Stream weights so grammar is a deliberate MINORITY (~1 in 6), not a coin flip
# that wins whenever the word streams are momentarily empty. We draw a weighted
# order and take the first stream that yields a card (so a dead stream doesn't
# waste the tick, and can't hand its share to grammar).
STREAM_WEIGHTS = {"repeat": 60, "review": 22, "new": 18, "grammar": 15}


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
    """A cloze answer is a single English word. Text that carries a translation
    separator or extra words is a quick-add, not an answer — leave it alone."""
    return bool(_CLOZE_ANSWER_RE.match(text.strip()))


_TYPED_CARDS = (CARD_CLOZE, CARD_TYPE_IN)
_QUICK_ADD_MARKS = ("|", " - ", " — ", " – ", "	")


def _looks_like_typed_answer(text: str, card_type: str | None) -> bool:
    """Whether this message is an answer to the card in flight.

    A cloze answer is one English word, so the old single-word test still holds
    there. A type-in answer can be a whole phrase — "Is it far from here?" — so
    the test instead asks whether it looks like English and carries none of the
    marks of a quick-add, which always pairs a word with a Russian translation.
    """
    body = (text or "").strip()
    if not body:
        return False
    if card_type == CARD_CLOZE:
        return _looks_like_cloze_answer(body)
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
        for uid in user_ids:
            user = await user_repo.get(uid)
            ut = await ut_repo.get(uid, _TRACK)
            if user is None or ut is None:
                continue
            if (ut.settings or {}).get("push_blocked"):
                continue  # user blocked the bot — stop trying (cleared on /start)
            if not user.level:
                # Held by the placement gate. Cards picked without a level would
                # be picked from a guess, which is what the gate is there to
                # stop — and pushing them anyway would make the block look broken.
                continue
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
                    state["inflight"] = None
                    state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
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
                )
                if new_msg_id:
                    old_msg_id = inflight.get("msg_id")
                    if old_msg_id:
                        await self._delete(user.telegram_id, old_msg_id)
                    inflight["msg_id"] = new_msg_id
                    inflight["retry_ts"] = now_ts + _retry_after(attempts)
                    sent = True
            await self._save(user.id, state)
            return sent

        # ---- no card pending: gated by the window + the post-answer gap ----
        if not win or now_ts < state.get("next_ts", 0.0):
            await self._save(user.id, state)
            return False

        # ---- a grammar rule waiting to be introduced? show it once, first ----
        rule_topic = await self._grammar.pending_rule(user.id, _TRACK)
        if rule_topic is not None:
            msg_id = await self._raw_send(
                user.telegram_id,
                PUSH_RULE_CARD.format(title=html.escape(rule_topic.title), rule=rule_topic.rule),
                push_rule_kb(),
            )
            if msg_id:
                await self._grammar.mark_rule_seen(user.id, rule_topic.id)
                state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
            await self._save(user.id, state)
            return msg_id is not None

        # ---- pick the next card: random among streams (words + grammar) ----
        #   "new" — introduce a new word (gated by today's intake + pool ceiling)
        #   "repeat" — reinforce a random word being learned
        #   "review" — a mastered word due for review
        #   "grammar" — a non-mastered grammar exercise
        # Don't serve the same card twice in a row — skip whatever was answered
        # last (a small active set + ORDER BY random() otherwise repeats a word).
        last = state.get("last") or {}
        last_word = int(last.get("id", 0)) if last.get("kind") == "word" else 0
        last_grammar = int(last.get("id", 0)) if last.get("kind") == "grammar" else 0

        # New-word intake is decoupled from mastering old words: introduce up to
        # `pace` new words per day, but only while the active pool stays under
        # `ceiling` (pace × 3) — so growth is steady, not a flood that turns the
        # push into mush. (Old rule gated new on a word hitting 10-in-a-row.)
        pace = pace_of(ut.settings)
        # The pool is sized by what the user actually answers, not by the pace
        # they picked once: `pace × 3` let user 1 sit on 63 active words at ~9
        # answers a day, so a word only came back every couple of weeks and
        # almost nothing ever stuck. See pacing.pool_ceiling.
        throughput = await self._reviews.typical_daily_answers(user.id, _TRACK)
        ceiling = pool_ceiling(throughput)
        new_today = int(state.get("new_today", 0))
        active_count = await self._uw.count_active(user.id, _TRACK)
        overdue = await self._uw.count_overdue(user.id, _TRACK)

        # Words are the bulk; grammar is a deliberate ~1-in-6 minority (STREAM_WEIGHTS),
        # never two grammar cards in a row, and never grabs an empty word stream's share.
        grammar_pick = await self._grammar.pick_for_push(user.id, _TRACK, exclude_id=last_grammar)
        eligible: list[str] = ["repeat", "review"]
        # Introduce a new word only if today's intake + pool ceiling allow AND the
        # review backlog isn't already piled up — draining due words first is what
        # lets them actually reach mastery instead of resurfacing once a week.
        if (
            new_today < pace
            and active_count < ceiling
            and overdue < self._s.push_review_backlog_ceiling
        ):
            eligible.append("new")
        allow_grammar = grammar_pick is not None and last.get("kind") != "grammar"
        if allow_grammar:
            eligible.append("grammar")

        sent = False
        for stream in _weighted_order(eligible):
            if stream == "grammar":
                ugi, _gi = grammar_pick
                msg_id, options, correct = await self._send_card(user, "grammar", ugi.id)
                if msg_id:
                    state["inflight"] = self._inflight("grammar", ugi.id, options, correct, now_ts, msg_id)
                    sent = True
                break
            if stream == "new":
                pick = await self._uw.pick_new_for_push(user.id, _TRACK, user.level)
            elif stream == "repeat":
                pick = await self._uw.pick_active_due(user.id, _TRACK, exclude_uw_id=last_word)
            else:
                pick = await self._uw.pick_review_mastered(user.id, _TRACK, exclude_uw_id=last_word)
            if pick is None:
                continue
            uw, _w = pick
            # Card type by production-ladder stage (recognition → reverse → cloze).
            ctype = self._card_type(uw, _w, user.level)
            msg_id, options, correct = await self._send_card(user, "word", uw.id, card_type=ctype)
            if msg_id:
                state["inflight"] = self._inflight("word", uw.id, options, correct, now_ts, msg_id, ctype=ctype)
                if stream == "new":
                    state["new_today"] = new_today + 1  # count an introduction
                sent = True
            break

        # Fallback: words couldn't fill the tick and we'd held grammar back only
        # to avoid two-in-a-row — use it rather than send nothing.
        if not sent and grammar_pick is not None and not allow_grammar:
            ugi, _gi = grammar_pick
            msg_id, options, correct = await self._send_card(user, "grammar", ugi.id)
            if msg_id:
                state["inflight"] = self._inflight("grammar", ugi.id, options, correct, now_ts, msg_id)
                sent = True

        await self._save(user.id, state)
        return sent

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
        msg_id = await self._raw_send(user.telegram_id, text, kb)
        return msg_id, options, correct

    async def _raw_send(self, telegram_id: int, text: str, reply_markup) -> int | None:
        """Send a push card with a prebuilt keyboard; return the new message_id
        (so retries can delete the previous one), or None on failure."""
        if self._bot is None:
            return None
        try:
            msg = await self._bot.send_message(
                telegram_id, text, reply_markup=reply_markup, parse_mode="HTML"
            )
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

        leech_writing: str | None = None
        recap = ""  # grammar cards have no word to recap
        if inflight.get("kind") == "grammar":
            await self._apply_grammar_answer(user, ut, iid, correct)
        else:
            outcome = await self._apply_word_answer(
                user, ut, iid, correct, card_type=inflight.get("ctype")
            )
            leech_writing, recap = outcome.leech_writing, outcome.recap

        now_ts = datetime.now(timezone.utc).timestamp()
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
    ) -> AnswerOutcome:
        """Apply a typed answer's SR result and advance the push state."""
        outcome = await self._apply_word_answer(
            user, ut, iid, correct,
            card_type=inflight.get("ctype") or CARD_CLOZE,
            kind_override=verdict.kind if verdict is not None else None,
        )
        now_ts = datetime.now(timezone.utc).timestamp()
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
            user, ut, iid, correct, state, inflight, verdict=verdict
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

    async def _apply_grammar_answer(self, user: User, ut: UserTrack, ugi_id: int, correct: bool) -> None:
        ugi = await self._grammar.get_user_item(ugi_id)
        if ugi is None:
            return
        was_mastered = ugi.status == WordStatus.MASTERED.value
        apply_review(ugi, ReviewResult.CORRECT if correct else ReviewResult.WRONG, LearningPace(ut.learning_pace))
        await self._grammar_reviews.create(
            user_id=user.id, track=_TRACK, user_grammar_item_id=ugi_id,
            result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
        )
        await self._session.flush()
        await ProgressService(self._session).update_streak(user)
        # Grammar item mastered → advance the course (next topic + word top-up).
        if not was_mastered and ugi.status == WordStatus.MASTERED.value:
            from app.services.course_service import CourseService

            await CourseService(self._session, self._redis).refill(user, ut, _TRACK)
