from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class LoggingContextMiddleware(BaseMiddleware):
    """Binds per-update identifiers into structlog contextvars.

    Every log line emitted while handling an update automatically carries
    `uid` / `chat` / `update_id` / `event`, so logs are traceable per user
    without each call site passing the ids manually. Context is cleared after
    the update so it never leaks between users.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        structlog.contextvars.clear_contextvars()
        ctx: dict[str, Any] = {"event": type(event).__name__}

        user = data.get("event_from_user")
        if user is not None:
            ctx["uid"] = user.id
        chat = data.get("event_chat")
        if chat is not None:
            ctx["chat"] = chat.id
        update = data.get("event_update")
        if update is not None:
            ctx["update_id"] = update.update_id

        structlog.contextvars.bind_contextvars(**ctx)
        try:
            return await handler(event, data)
        finally:
            structlog.contextvars.clear_contextvars()
