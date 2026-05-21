from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.infrastructure.repositories.users import UserRepository


class UserLoaderMiddleware(BaseMiddleware):
    """Loads or creates the User row and injects it into handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user is None:
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return await handler(event, data)

        repo = UserRepository(session)
        user, _ = await repo.upsert_by_telegram_id(
            telegram_id=tg_user.id,
            language=(tg_user.language_code or "ru")[:8],
        )
        data["user"] = user
        return await handler(event, data)
