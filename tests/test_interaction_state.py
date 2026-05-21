from __future__ import annotations

import json
from typing import Any

import pytest

from app.bot.states import InteractionState
from app.services.interaction_state_service import InteractionStateService, StatePayload


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttl[key] = ex

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttl.pop(key, None)


@pytest.fixture
def service() -> InteractionStateService:
    return InteractionStateService(FakeRedis())  # type: ignore[arg-type]


async def test_default_state_is_idle(service: InteractionStateService):
    payload = await service.get(123)
    assert payload.state == InteractionState.IDLE
    assert payload.data == {}


async def test_set_then_get(service: InteractionStateService):
    await service.set(123, InteractionState.WAITING_MANUAL_WORDS, {"k": "v"})
    payload = await service.get(123)
    assert payload.state == InteractionState.WAITING_MANUAL_WORDS
    assert payload.data == {"k": "v"}


async def test_setting_idle_clears(service: InteractionStateService):
    await service.set(123, InteractionState.WAITING_MANUAL_WORDS)
    await service.set(123, InteractionState.IDLE)
    payload = await service.get(123)
    assert payload.state == InteractionState.IDLE


async def test_update_data_keeps_state(service: InteractionStateService):
    await service.set(123, InteractionState.PACK_SELECTION, {"selected": ["IT"]})
    await service.update_data(123, selected=["IT", "Crypto"])
    payload = await service.get(123)
    assert payload.state == InteractionState.PACK_SELECTION
    assert payload.data == {"selected": ["IT", "Crypto"]}


async def test_clear(service: InteractionStateService):
    await service.set(123, InteractionState.WAITING_MANUAL_WORDS)
    await service.clear(123)
    payload = await service.get(123)
    assert payload.state == InteractionState.IDLE


async def test_corrupt_payload_falls_back_to_idle(service: InteractionStateService):
    # Simulate corrupt JSON in Redis.
    await service._redis.set(service._key(123), "not-json")  # type: ignore[attr-defined]
    payload = await service.get(123)
    assert payload.state == InteractionState.IDLE
