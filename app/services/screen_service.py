from __future__ import annotations

import secrets

from redis.asyncio import Redis


SCREEN_KEY = "screen:{user_id}:{kind}"
SCREEN_TTL = 86400  # 24h — long enough for stale buttons to age out


class ScreenVersionService:
    """Tracks the current valid 'version' token for a given screen kind per user.

    Each time we render an interactive screen we bump the version. The version is
    embedded in callback_data; stale callbacks from earlier renders are rejected.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, user_id: int, kind: str) -> str:
        return SCREEN_KEY.format(user_id=user_id, kind=kind)

    async def bump(self, user_id: int, kind: str) -> str:
        # 3 bytes = 4 base64url chars — small enough to be embedded in
        # multiple callback_data fields without busting the 64-byte budget.
        v = secrets.token_urlsafe(3)
        await self._redis.set(self._key(user_id, kind), v, ex=SCREEN_TTL)
        return v

    async def current(self, user_id: int, kind: str) -> str | None:
        return await self._redis.get(self._key(user_id, kind))

    async def check(self, user_id: int, kind: str, version: str) -> bool:
        cur = await self.current(user_id, kind)
        return cur is not None and cur == version
