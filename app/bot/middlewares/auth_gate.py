from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.states import InteractionState
from app.bot.texts import PASSWORD_REQUIRED_HINT
from app.services.interaction_state_service import InteractionStateService


class AuthGateMiddleware(BaseMiddleware):
    """Blocks all interactions for users who haven't entered the access password.

    Allowed always for unauthorized users:
      - /start command (lets them enter the gate flow)
      - Text messages while the user is in WAITING_PASSWORD state (their attempt)

    Everything else is rejected with a short hint.
    """

    def __init__(self, access_password: str, state_service: InteractionStateService) -> None:
        self._enabled = bool(access_password)
        self._state_service = state_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self._enabled:
            return await handler(event, data)

        user = data.get("user")
        if user is None or getattr(user, "is_authorized", False):
            return await handler(event, data)

        if isinstance(event, Message):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
            payload = await self._state_service.get(user.id)
            if payload.state == InteractionState.WAITING_PASSWORD and event.text is not None:
                return await handler(event, data)
            await event.answer(PASSWORD_REQUIRED_HINT)
            return None

        if isinstance(event, CallbackQuery):
            await event.answer(PASSWORD_REQUIRED_HINT, show_alert=False)
            return None

        return None
