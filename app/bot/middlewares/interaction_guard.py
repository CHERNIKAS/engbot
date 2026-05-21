from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.states import (
    DOCUMENT_ACCEPTING_STATES,
    STATE_CALLBACK_PREFIXES,
    TEXT_ACCEPTING_STATES,
    UNIVERSAL_PREFIXES,
    InteractionState,
)
from app.bot.texts import CONFLICT_STATE
from app.services.interaction_state_service import InteractionStateService


class InteractionGuardMiddleware(BaseMiddleware):
    """Blocks handlers that don't match the user's current interaction state.

    Allowed always:
      - Universal callback prefixes (nav, noop).
      - `/start` command (separately handled).

    Otherwise:
      - For callback queries, prefix must be in STATE_CALLBACK_PREFIXES[state].
      - For text messages, the state must accept text.
      - For documents, the state must accept documents.
    """

    def __init__(self, state_service: InteractionStateService) -> None:
        self._state_service = state_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is None:
            return await handler(event, data)

        payload = await self._state_service.get(user.id)
        data["interaction_state"] = payload

        if isinstance(event, CallbackQuery):
            prefix = (event.data or "").split(":", 1)[0]
            if prefix in UNIVERSAL_PREFIXES:
                return await handler(event, data)
            allowed = STATE_CALLBACK_PREFIXES.get(payload.state, frozenset())
            if prefix not in allowed:
                await event.answer(CONFLICT_STATE, show_alert=False)
                return None
            return await handler(event, data)

        if isinstance(event, Message):
            # /start always allowed (handled separately).
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)

            if event.document is not None:
                if payload.state not in DOCUMENT_ACCEPTING_STATES:
                    await event.answer(CONFLICT_STATE)
                    return None
                return await handler(event, data)

            if event.text is not None:
                if payload.state not in TEXT_ACCEPTING_STATES:
                    await event.answer(CONFLICT_STATE)
                    return None
                return await handler(event, data)

        return await handler(event, data)
