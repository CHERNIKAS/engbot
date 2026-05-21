from __future__ import annotations

import pytest

from app.domain.enums import LearningTrack
from app.services.track_context_service import TrackContextService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture
def service() -> TrackContextService:
    return TrackContextService(FakeRedis())  # type: ignore[arg-type]


async def test_default_is_english(service: TrackContextService):
    assert await service.get(1) == LearningTrack.ENGLISH


async def test_set_then_get(service: TrackContextService):
    await service.set(1, LearningTrack.JAPANESE)
    assert await service.get(1) == LearningTrack.JAPANESE


async def test_clear_resets_to_default(service: TrackContextService):
    await service.set(1, LearningTrack.JAPANESE)
    await service.clear(1)
    assert await service.get(1) == LearningTrack.ENGLISH


async def test_invalid_stored_value_falls_back(service: TrackContextService):
    await service._redis.set(service._key(1), "klingon")  # type: ignore[attr-defined]
    assert await service.get(1) == LearningTrack.ENGLISH
