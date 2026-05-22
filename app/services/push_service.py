from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.push import SNOOZE_LABELS, push_card_kb, push_schedule_prompt_kb
from app.bot.texts import (
    PUSH_ANSWER_CORRECT,
    PUSH_ANSWER_WRONG,
    PUSH_CARD,
    PUSH_HIDDEN,
    PUSH_KNOWN,
    PUSH_SCHEDULE_PROMPT,
    PUSH_SNOOZED,
    PUSH_STALE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult, WordStatus
from app.domain.models import User, UserTrack
from app.domain.push import in_window, normalize_window
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.logging_setup import get_logger
from app.services.progress_service import ProgressService
from app.services.repetition_service import apply_review

log = get_logger("push")

_KEY = "push:{user_id}"
_TTL = 172_800  # 2 days
_TRACK = LearningTrack.ENGLISH


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _minutes(a: int, b: int) -> float:
    return random.randint(a, b) * 60.0


def _progress_line(uw) -> str:
    """Small progress hint shown under the word on a push card."""
    if uw.status == WordStatus.MASTERED.value:
        return f"⭐ {uw.mastery_score:.1f} / 5"
    return f"🌱 {uw.repetitions_count} / 10"


class PushService:
    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot | None = None) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot
        self._uw = UserWordRepository(session)
        self._reviews = WordReviewRepository(session)
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

    def _window(self, ut: UserTrack) -> tuple[int, int]:
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
        ut_repo = UserTrackRepository(self._session)
        pushed = 0
        for user in await UserRepository(self._session).list_for_reminders():
            ut = await ut_repo.get(user.id, _TRACK)
            if ut is None:
                continue
            try:
                if await self.run_tick(user, ut):
                    pushed += 1
            except Exception:  # noqa: BLE001
                log.warning("push_tick_failed", uid=user.id)
        return pushed

    async def run_tick(self, user: User, ut: UserTrack) -> bool:
        ws, we = self._window(ut)
        now = datetime.now(timezone.utc)
        local = now.astimezone(_tz(user.timezone))
        now_ts = now.timestamp()
        today = local.date().isoformat()

        state = await self._load(user.id)
        if state.get("day") != today:
            state = {"day": today, "next_ts": 0.0, "inflight": None, "sched_asked": state.get("sched_asked", "")}

        win = in_window(local.hour, ws, we)

        # Daily "keep / change schedule?" prompt — once per day, in window.
        if win and state.get("sched_asked") != today and self._bot is not None:
            try:
                await self._bot.send_message(
                    user.telegram_id,
                    PUSH_SCHEDULE_PROMPT.format(ws=ws, we=we),
                    reply_markup=push_schedule_prompt_kb(),
                    parse_mode="HTML",
                )
                state["sched_asked"] = today
            except Exception:  # noqa: BLE001
                log.warning("push_prompt_failed", uid=user.id)

        inflight = state.get("inflight")

        # ---- a card is waiting for an answer: keep nudging the SAME word until
        #      the user replies (the "force"); replace the old message each time.
        if inflight is not None:
            sent = False
            if win and now_ts >= inflight.get("retry_ts", 0):
                new_msg_id = await self._send(user, inflight["uw_id"], inflight["options"])
                if new_msg_id:
                    old_msg_id = inflight.get("msg_id")
                    if old_msg_id:
                        await self._delete(user.telegram_id, old_msg_id)
                    inflight["msg_id"] = new_msg_id
                    inflight["retry_ts"] = now_ts + _minutes(
                        self._s.push_retry_min_minutes, self._s.push_retry_max_minutes
                    )
                    sent = True
            await self._save(user.id, state)
            return sent

        # ---- no card pending: gated by the window + the post-answer gap ----
        if not win or now_ts < state.get("next_ts", 0.0):
            await self._save(user.id, state)
            return False

        # ---- pick the next card: random among three streams ----
        #   "new"    — introduce a new word, only if the active set has room
        #              (words being learned < daily goal). One out, one in.
        #   "repeat" — reinforce a random word currently being learned.
        #   "review" — a mastered word whose spaced-repetition review is due.
        active_count = await self._uw.count_active(user.id, _TRACK)
        streams: list[str] = ["repeat", "review"]
        if active_count < ut.daily_goal_words:
            streams.append("new")
        random.shuffle(streams)

        sent = False
        for stream in streams:
            if stream == "new":
                pick = await self._uw.pick_new_for_push(user.id, _TRACK)
            elif stream == "repeat":
                pick = await self._uw.pick_active_random(user.id, _TRACK)
            else:
                pick = await self._uw.pick_review_mastered(user.id, _TRACK)
            if pick is None:
                continue
            uw, _w = pick
            card = await self._build_card(user.id, uw.id)
            if card is None:
                continue
            text, options, correct, status = card
            msg_id = await self._raw_send(user.telegram_id, text, options, uw.id, status)
            if msg_id:
                state["inflight"] = self._inflight(uw.id, options, correct, now_ts, msg_id)
                sent = True
            break

        await self._save(user.id, state)
        return sent

    def _inflight(
        self, uw_id: int, options: list[str], correct: str, now_ts: float, msg_id: int | None = None
    ) -> dict:
        return {
            "uw_id": uw_id,
            "options": options,
            "correct": correct,
            "msg_id": msg_id,
            "retry_ts": now_ts + _minutes(self._s.push_retry_min_minutes, self._s.push_retry_max_minutes),
        }

    async def _send(self, user: User, uw_id: int, options: list[str]) -> int | None:
        card = await self._build_card(user.id, uw_id)
        text = card[0] if card else PUSH_CARD.format(word="…")
        status = card[3] if card else WordStatus.NEW.value
        return await self._raw_send(user.telegram_id, text, options, uw_id, status)

    async def _raw_send(
        self, telegram_id: int, text: str, options: list[str], uw_id: int, status: str
    ) -> int | None:
        """Send a push card; return the new message_id (so retries can delete the
        previous one), or None on failure."""
        if self._bot is None:
            return None
        try:
            msg = await self._bot.send_message(
                telegram_id, text, reply_markup=push_card_kb(options, uw_id, status), parse_mode="HTML"
            )
            return msg.message_id
        except Exception:  # noqa: BLE001 — user may have blocked the bot
            log.warning("push_send_failed", tg=telegram_id)
            return None

    async def _delete(self, chat_id: int, message_id: int) -> None:
        if self._bot is None:
            return
        try:
            await self._bot.delete_message(chat_id, message_id)
        except Exception:  # noqa: BLE001 — message may already be gone / too old
            pass

    async def _build_card(
        self, user_id: int, uw_id: int
    ) -> tuple[str, list[str], str, str] | None:
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return None
        uw, word = pair
        correct = uw.custom_translation or word.translation
        if not correct:
            return None
        distractors = await self._uw.quiz_distractors(
            user_id, track=_TRACK, exclude_user_word_id=uw_id, limit=3, exclude_translations=[correct]
        )
        options = [correct, *distractors[:3]]
        random.shuffle(options)
        text = f"{PUSH_CARD.format(word=word.writing)}\n<i>{_progress_line(uw)}</i>"
        return text, options, correct, uw.status

    # ---- card controls (handler path): я знаю / перестать показывать / отложить ----

    async def handle_remove(self, user: User, uw_id: int, query: CallbackQuery, *, known: bool) -> None:
        uw = await self._uw.get(uw_id)
        if uw is not None:
            uw.archived = True
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_KNOWN if known else PUSH_HIDDEN)

    async def handle_snooze(self, user: User, uw_id: int, days: int, query: CallbackQuery) -> None:
        uw = await self._uw.get(uw_id)
        if uw is not None:
            uw.snooze_until = datetime.now(timezone.utc) + timedelta(days=days)
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_SNOOZED.format(label=SNOOZE_LABELS.get(days, f"{days} дн.")))

    async def _advance_after_card(self, user_id: int, uw_id: int) -> None:
        """Drop the current card and let the next one come on the next worker tick."""
        state = await self._load(user_id)
        inflight = state.get("inflight")
        if inflight and int(inflight.get("uw_id", 0)) == uw_id:
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
        if not inflight or int(inflight.get("uw_id", 0)) != uw_id:
            await query.answer(PUSH_STALE, show_alert=False)
            return
        options = inflight.get("options") or []
        if idx < 0 or idx >= len(options):
            await query.answer()
            return
        correct = options[idx] == inflight.get("correct")

        uw = await self._uw.get(uw_id)
        if uw is not None:
            apply_review(
                uw,
                ReviewResult.CORRECT if correct else ReviewResult.WRONG,
                LearningPace(ut.learning_pace),
            )
            await self._reviews.create(
                user_id=user.id, track=_TRACK, user_word_id=uw_id,
                session_id=None, result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
            )
            await self._session.flush()
            await ProgressService(self._session).update_streak(user)

        now_ts = datetime.now(timezone.utc).timestamp()
        state["inflight"] = None
        state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
        await self._save(user.id, state)

        feedback = PUSH_ANSWER_CORRECT if correct else PUSH_ANSWER_WRONG.format(answer=inflight.get("correct"))
        if query.message:
            try:
                await query.message.edit_text(feedback, parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        await query.answer("✅" if correct else "❌")
