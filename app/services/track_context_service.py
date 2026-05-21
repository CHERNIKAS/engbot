from __future__ import annotations

from redis.asyncio import Redis

from app.domain.enums import LearningTrack


CURRENT_TRACK_KEY = "current_track:{user_id}"
TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — current-track is a soft preference


class TrackContextService:
    """Stores the user's currently active learning track in Redis.

    PostgreSQL is the source of truth for what tracks a user has *enabled*; this
    Redis cache only stores which one is "in focus" for the current UX.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, user_id: int) -> str:
        return CURRENT_TRACK_KEY.format(user_id=user_id)

    async def get(self, user_id: int) -> LearningTrack:
        raw = await self._redis.get(self._key(user_id))
        if not raw:
            return LearningTrack.ENGLISH
        try:
            return LearningTrack(raw)
        except ValueError:
            return LearningTrack.ENGLISH

    async def set(self, user_id: int, track: LearningTrack) -> None:
        await self._redis.set(self._key(user_id), track.value, ex=TTL_SECONDS)

    async def clear(self, user_id: int) -> None:
        await self._redis.delete(self._key(user_id))
