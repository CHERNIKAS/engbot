from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.bot.states import InteractionState
from app.config import get_settings


STATE_KEY = "state:{user_id}"


@dataclass
class StatePayload:
    state: InteractionState = InteractionState.IDLE
    data: dict[str, Any] = field(default_factory=dict)


class InteractionStateService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._ttl = get_settings().interaction_ttl_seconds
        self._study_ttl = get_settings().study_ttl_seconds

    def _key(self, user_id: int) -> str:
        return STATE_KEY.format(user_id=user_id)

    async def get(self, user_id: int) -> StatePayload:
        raw = await self._redis.get(self._key(user_id))
        if not raw:
            return StatePayload()
        try:
            parsed = json.loads(raw)
            return StatePayload(
                state=InteractionState(parsed.get("state", InteractionState.IDLE.value)),
                data=parsed.get("data", {}) or {},
            )
        except (json.JSONDecodeError, ValueError):
            await self.clear(user_id)
            return StatePayload()

    async def set(
        self,
        user_id: int,
        state: InteractionState,
        data: dict[str, Any] | None = None,
        ttl: int | None = None,
    ) -> None:
        ttl = ttl if ttl is not None else (
            self._study_ttl if state == InteractionState.STUDY_ACTIVE else self._ttl
        )
        if state == InteractionState.IDLE:
            await self.clear(user_id)
            return
        payload = json.dumps({"state": state.value, "data": data or {}}, ensure_ascii=False)
        await self._redis.set(self._key(user_id), payload, ex=ttl)

    async def update_data(self, user_id: int, **values: Any) -> StatePayload:
        current = await self.get(user_id)
        if current.state == InteractionState.IDLE:
            return current
        current.data.update(values)
        await self.set(user_id, current.state, current.data)
        return current

    async def clear(self, user_id: int) -> None:
        await self._redis.delete(self._key(user_id))

    async def assert_in(self, user_id: int, allowed: set[InteractionState]) -> bool:
        current = await self.get(user_id)
        return current.state in allowed
