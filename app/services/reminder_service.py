from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.study import study_now_kb
from app.bot.texts import REMINDER_DAILY, REMINDER_INACTIVE, REMINDER_STREAK
from app.config import get_settings
from app.domain.enums import LearningTrack
from app.domain.reminders import ReminderKind, decide_reminder
from app.infrastructure.repositories.user_tracks import UserTrackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.users import UserRepository
from app.logging_setup import get_logger
from app.services.progress_service import ProgressService

log = get_logger("reminders")

_REMINDED_KEY = "reminded:{user_id}:{day}"
_REMINDED_TTL = 90_000  # ~25h


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class ReminderService:
    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot

    async def run(self) -> int:
        settings = get_settings()
        if not settings.reminders_enabled:
            return 0

        now = datetime.now(timezone.utc)
        users = await UserRepository(self._session).list_for_reminders()
        progress = ProgressService(self._session)
        ut_repo = UserTrackRepository(self._session)
        uw_repo = UserWordRepository(self._session)
        track = LearningTrack.ENGLISH
        sent = 0

        for user in users:
            local = now.astimezone(_tz(user.timezone))
            if not (settings.reminder_window_start <= local.hour < settings.reminder_window_end):
                continue
            day_key = _REMINDED_KEY.format(user_id=user.id, day=local.date().isoformat())
            if await self._redis.exists(day_key):
                continue

            total = await uw_repo.total_for_user(user.id, track)
            if total == 0:
                continue  # nothing to study — nothing to remind about

            ut = await ut_repo.get(user.id, track)
            goal = ut.daily_goal_words if ut else settings.default_daily_goal
            studied = await progress.studied_today_count(user.id, track, tz_name=user.timezone)
            days_since = (
                (local.date() - user.last_study_date).days if user.last_study_date else None
            )

            kind = decide_reminder(
                studied_today=studied,
                daily_goal=goal,
                streak_days=user.streak_days,
                days_since_study=days_since,
                local_hour=local.hour,
                window_start=settings.reminder_window_start,
                window_end=settings.reminder_window_end,
            )
            if kind is None:
                continue

            try:
                await self._bot.send_message(
                    user.telegram_id,
                    _text(kind, studied, goal, user.streak_days),
                    reply_markup=study_now_kb(),
                )
                await self._redis.set(day_key, "1", ex=_REMINDED_TTL)
                sent += 1
            except Exception:  # noqa: BLE001 — user may have blocked the bot
                log.warning("reminder_send_failed", uid=user.id)

        return sent


def _text(kind: ReminderKind, studied: int, goal: int, streak: int) -> str:
    if kind == ReminderKind.STREAK:
        return REMINDER_STREAK.format(streak=streak)
    if kind == ReminderKind.INACTIVE:
        return REMINDER_INACTIVE
    return REMINDER_DAILY.format(studied=studied, goal=goal, left=max(0, goal - studied))
