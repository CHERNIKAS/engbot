from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import TelegramObject

from app.bot.states import InteractionState
from app.services.interaction_state_service import StatePayload


class InState(Filter):
    """Filter that matches when the user's current interaction state is in `allowed`.

    Reads `interaction_state` from middleware data (set by InteractionGuardMiddleware).
    """

    def __init__(self, *allowed: InteractionState) -> None:
        self._allowed = frozenset(allowed)

    async def __call__(self, event: TelegramObject, interaction_state: StatePayload | None = None, **_: object) -> bool:
        if interaction_state is None:
            return False
        return interaction_state.state in self._allowed
