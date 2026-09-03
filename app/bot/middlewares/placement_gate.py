"""Holds the bot closed until the user has a CEFR level.

Selection, the mastery bar and the card ladder all key off `users.level`. A user
without one silently falls back to a default, which is the guess the placement
test exists to replace — so rather than teach them from a guess, the bot asks
for one minute of their time first.

Only bites users who finished onboarding before the test existed: new users meet
it inside onboarding, and by the time they're through they already have a level.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.keyboards.onboarding import placement_gate_kb
from app.bot.texts import PLACEMENT_GATE, PLACEMENT_GATE_HINT

# Callback prefixes the gate always lets through: taking the test, and answering
# its cards. Everything else — menus, drills, push answers — waits.
_ALLOWED_CALLBACK_PREFIXES = ("ob:lvl_gate", "ob:lvl:")


class PlacementGateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is None:
            return await handler(event, data)
        # Not onboarded yet: onboarding runs the test itself, and blocking here
        # would lock a new user out of the very flow that would free them.
        if not getattr(user, "onboarding_completed", False):
            return await handler(event, data)
        if getattr(user, "level", None):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if (event.data or "").startswith(_ALLOWED_CALLBACK_PREFIXES):
                return await handler(event, data)
            await event.answer(PLACEMENT_GATE_HINT, show_alert=False)
            return None

        if isinstance(event, Message):
            # Any message — /start, a menu tap, a typed answer — gets the same
            # screen with the only button that moves them forward.
            await event.answer(
                PLACEMENT_GATE,
                reply_markup=placement_gate_kb(),
            )
            return None

        return None
