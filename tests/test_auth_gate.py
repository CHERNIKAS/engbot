from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from app.bot.middlewares.auth_gate import AuthGateMiddleware
from app.bot.states import InteractionState
from app.services.interaction_state_service import InteractionStateService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


def _fake_message(text: str | None = None) -> Message:
    """MagicMock(spec=Message) passes isinstance(..., Message) checks."""
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.document = None
    msg.answer = AsyncMock()
    return msg


def _fake_callback() -> CallbackQuery:
    cb = MagicMock(spec=CallbackQuery)
    cb.data = "mm:words"
    cb.answer = AsyncMock()
    return cb


@pytest.fixture
def state_service() -> InteractionStateService:
    return InteractionStateService(FakeRedis())  # type: ignore[arg-type]


async def _call(
    gate: AuthGateMiddleware, event: Any, data: dict[str, Any]
) -> tuple[bool, Any]:
    called = {"v": False}

    async def handler(_e: Any, _d: dict[str, Any]) -> str:
        called["v"] = True
        return "downstream"

    result = await gate(handler, event, data)
    return called["v"], result


async def test_empty_password_disables_gate_for_unauthorized_user(state_service):
    gate = AuthGateMiddleware(access_password="", state_service=state_service)
    user = SimpleNamespace(id=1, is_authorized=False)

    msg = _fake_message(text="hello there")
    called, _ = await _call(gate, msg, {"user": user})
    assert called is True
    msg.answer.assert_not_called()

    cb = _fake_callback()
    called, _ = await _call(gate, cb, {"user": user})
    assert called is True
    cb.answer.assert_not_called()


async def test_password_set_blocks_unauthorized_callback(state_service):
    gate = AuthGateMiddleware(access_password="hunter2", state_service=state_service)
    user = SimpleNamespace(id=1, is_authorized=False)

    cb = _fake_callback()
    called, _ = await _call(gate, cb, {"user": user})
    assert called is False
    cb.answer.assert_called_once()


async def test_password_set_allows_start_command(state_service):
    gate = AuthGateMiddleware(access_password="hunter2", state_service=state_service)
    user = SimpleNamespace(id=1, is_authorized=False)
    msg = _fake_message(text="/start")
    called, _ = await _call(gate, msg, {"user": user})
    assert called is True


async def test_password_set_allows_text_in_waiting_password_state(state_service):
    gate = AuthGateMiddleware(access_password="hunter2", state_service=state_service)
    user = SimpleNamespace(id=42, is_authorized=False)
    await state_service.set(user.id, InteractionState.WAITING_PASSWORD)

    msg = _fake_message(text="hunter2")
    called, _ = await _call(gate, msg, {"user": user})
    assert called is True


async def test_authorized_user_passes_regardless_of_password(state_service):
    gate = AuthGateMiddleware(access_password="hunter2", state_service=state_service)
    user = SimpleNamespace(id=1, is_authorized=True)

    cb = _fake_callback()
    called, _ = await _call(gate, cb, {"user": user})
    assert called is True
