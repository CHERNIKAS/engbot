from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

RATE_KEY = "rl:{user_id}"


class RateLimitMiddleware(BaseMiddleware):
    """Token-bucket-ish rate limit per user using INCR + EXPIRE."""

    def __init__(self, redis: Redis, per_second: int = 5) -> None:
        self._redis = redis
        self._limit = per_second

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None:
            return await handler(event, data)

        key = RATE_KEY.format(user_id=user_id)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 1)
        if count > self._limit:
            if isinstance(event, CallbackQuery):
                await event.answer("Слишком быстро. Подожди секунду.", show_alert=False)
            return None
        return await handler(event, data)
