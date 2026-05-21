from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.push import push_card_kb, push_schedule_prompt_kb
from app.bot.texts import (
    PUSH_ANSWER_CORRECT,
    PUSH_ANSWER_WRONG,
    PUSH_CARD,
    PUSH_SCHEDULE_PROMPT,
    PUSH_STALE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult
from app.domain.models import User, UserTrack
from app.domain.push import in_window, normalize_window, plan_next
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
        from app.infrastructure.repositories.user_tracks import UserTrackRepository

        if self._bot is None:
            return 0
        pushed = 0
        for user, ut in await UserTrackRepository(self._session).list_push_enabled():
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
            state = {"day": today, "new_today": 0, "next_ts": 0.0, "inflight": None, "repeats": [], "sched_asked": state.get("sched_asked", "")}

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
        repeats = state.get("repeats", [])
        repeat_due = any(r.get("due_ts", 0) <= now_ts and r.get("left", 0) > 0 for r in repeats)

        action = plan_next(
            in_window_now=win,
            has_inflight=inflight is not None,
            inflight_retry_due=bool(inflight) and now_ts >= inflight.get("retry_ts", 0),
            gap_due=now_ts >= state.get("next_ts", 0.0),
            repeat_due=repeat_due,
            new_allowed=True,
        )

        sent = False
        if action == "retry" and inflight:
            sent = await self._send(user, inflight["uw_id"], inflight["options"], retry=True)
            if sent:
                inflight["attempts"] = inflight.get("attempts", 1) + 1
                inflight["retry_ts"] = now_ts + _minutes(self._s.push_retry_min_minutes, self._s.push_retry_max_minutes)
        elif action == "repeat":
            rep = min((r for r in repeats if r.get("due_ts", 0) <= now_ts and r.get("left", 0) > 0), key=lambda r: r["due_ts"], default=None)
            if rep:
                card = await self._build_card(user.id, rep["uw_id"])
                if card is None:
                    repeats.remove(rep)
                else:
                    text, options, correct = card
                    if await self._raw_send(user.telegram_id, text, options, rep["uw_id"]):
                        state["inflight"] = self._inflight(rep["uw_id"], options, correct, now_ts)
                        rep["left"] -= 1
                        if rep["left"] <= 0:
                            repeats.remove(rep)
                        sent = True
        elif action == "new":
            new_left = max(0, ut.daily_goal_words - state.get("new_today", 0))
            pick = await self._uw.pick_for_push(user.id, _TRACK, new_left)
            if pick is not None:
                uw, _w, is_new = pick
                card = await self._build_card(user.id, uw.id)
                if card is not None:
                    text, options, correct = card
                    if await self._raw_send(user.telegram_id, text, options, uw.id):
                        state["inflight"] = self._inflight(uw.id, options, correct, now_ts)
                        if is_new:
                            state["new_today"] = state.get("new_today", 0) + 1
                        sent = True

        state["repeats"] = repeats
        await self._save(user.id, state)
        return sent

    def _inflight(self, uw_id: int, options: list[str], correct: str, now_ts: float) -> dict:
        return {
            "uw_id": uw_id,
            "options": options,
            "correct": correct,
            "retry_ts": now_ts + _minutes(self._s.push_retry_min_minutes, self._s.push_retry_max_minutes),
            "attempts": 1,
        }

    async def _send(self, user: User, uw_id: int, options: list[str], *, retry: bool) -> bool:
        card = await self._build_card(user.id, uw_id)
        text = card[0] if card else PUSH_CARD.format(word="…")
        return await self._raw_send(user.telegram_id, text, options, uw_id)

    async def _raw_send(self, telegram_id: int, text: str, options: list[str], uw_id: int) -> bool:
        if self._bot is None:
            return False
        try:
            await self._bot.send_message(
                telegram_id, text, reply_markup=push_card_kb(options, uw_id), parse_mode="HTML"
            )
            return True
        except Exception:  # noqa: BLE001 — user may have blocked the bot
            log.warning("push_send_failed", tg=telegram_id)
            return False

    async def _build_card(self, user_id: int, uw_id: int) -> tuple[str, list[str], str] | None:
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
        return PUSH_CARD.format(word=word.writing), options, correct

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
        repeats = state.get("repeats", [])
        repeats.append({
            "uw_id": uw_id,
            "due_ts": now_ts + _minutes(self._s.push_gap_max_minutes, self._s.push_gap_max_minutes * 2),
            "left": self._s.push_repeats_per_word,
        })
        state["repeats"] = repeats
        await self._save(user.id, state)

        feedback = PUSH_ANSWER_CORRECT if correct else PUSH_ANSWER_WRONG.format(answer=inflight.get("correct"))
        if query.message:
            try:
                await query.message.edit_text(feedback, parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        await query.answer("✅" if correct else "❌")
