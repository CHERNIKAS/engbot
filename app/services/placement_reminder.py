"""A daily nudge for users the placement gate is holding.

They finished onboarding before the test existed, so `users.level` is NULL and
the bot answers everything with "take the test first". One announcement went
out and three days later none of the eight had taken it — a message sent once,
at one moment, is easy to miss.

So it repeats, but not forever. A reminder that keeps arriving after someone
has decided to ignore it stops being a reminder, so it stops on its own after
a handful of tries; the gate screen still greets them whenever they come back.
Sent inside the user's own daytime window — a nag at 4am is how a bot gets
blocked rather than opened.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.onboarding import placement_gate_kb
from app.bot.texts import PLACEMENT_GATE
from app.config import get_settings
from app.domain.models import User
from app.logging_setup import get_logger

log = get_logger("placement_reminder")

# One per user per local day.
_SENT_KEY = "plreminder:{user_id}:{day}"
_SENT_TTL = 172_800  # 2 days — long enough to cover any timezone's "today"
# How many times in total we're willing to ask. After this the gate screen is
# the only thing that mentions it: they've seen the message five times and
# chosen not to act, and a sixth is just noise.
_MAX_REMINDERS = 5
_COUNT_KEY = "plreminder:count:{user_id}"
_COUNT_TTL = 2_592_000  # 30 days


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class PlacementReminderService:
    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot

    async def run(self, now: datetime | None = None) -> int:
        """Nudge everyone the gate is holding, at most once per local day."""
        settings = get_settings()
        now = now or datetime.now(timezone.utc)
        blocked = (
            await self._session.execute(
                select(User).where(
                    User.level.is_(None),
                    User.onboarding_completed.is_(True),
                )
            )
        ).scalars().all()

        sent = 0
        for user in blocked:
            local = now.astimezone(_tz(user.timezone))
            if not (
                settings.push_default_window_start
                <= local.hour
                < settings.push_default_window_end
            ):
                continue
            day_key = _SENT_KEY.format(user_id=user.id, day=local.date().isoformat())
            if await self._redis.exists(day_key):
                continue

            count_key = _COUNT_KEY.format(user_id=user.id)
            already = int(await self._redis.get(count_key) or 0)
            if already >= _MAX_REMINDERS:
                # Mark the day anyway so we stop re-checking them every tick.
                await self._redis.set(day_key, "1", ex=_SENT_TTL)
                continue

            try:
                await self._bot.send_message(
                    user.telegram_id, PLACEMENT_GATE, reply_markup=placement_gate_kb()
                )
                sent += 1
            except TelegramForbiddenError:
                # Blocked the bot. Burn the whole allowance rather than retrying
                # daily into a closed door.
                await self._redis.set(count_key, str(_MAX_REMINDERS), ex=_COUNT_TTL)
            except Exception as exc:  # noqa: BLE001 — one bad send, not the batch
                log.warning("placement_reminder_failed", uid=user.id, error=repr(exc))
            else:
                await self._redis.set(count_key, str(already + 1), ex=_COUNT_TTL)
            await self._redis.set(day_key, "1", ex=_SENT_TTL)

        if sent:
            log.info("placement_reminders_sent", count=sent)
        return sent
