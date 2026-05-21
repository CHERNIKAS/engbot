from __future__ import annotations

from app.domain.enums import LearningPace, LearningTrack
from app.domain.models import UserTrack
from app.infrastructure.repositories.user_tracks import UserTrackRepository
from app.services.user_service import UserService


class UserTrackService:
    def __init__(self, repo: UserTrackRepository) -> None:
        self._repo = repo

    async def get_or_create(self, user_id: int, track: LearningTrack) -> UserTrack:
        ut = await self._repo.get(user_id, track)
        if ut is not None:
            return ut
        return await self._repo.upsert(user_id, track, is_active=True)

    async def get(self, user_id: int, track: LearningTrack) -> UserTrack | None:
        return await self._repo.get(user_id, track)

    async def list_active(self, user_id: int) -> list[UserTrack]:
        return await self._repo.list_active(user_id)

    async def set_active_tracks(self, user_id: int, active: set[LearningTrack]) -> None:
        # Ensure rows for both tracks; toggle is_active accordingly.
        for t in LearningTrack:
            await self._repo.set_active(user_id, t, t in active)

    async def set_daily_goal(self, user_id: int, track: LearningTrack, value: int) -> UserTrack:
        if not UserService.is_valid_goal(value):
            raise ValueError("invalid_goal")
        return await self._repo.upsert(user_id, track, daily_goal_words=value)

    async def set_pace(self, user_id: int, track: LearningTrack, pace: LearningPace) -> UserTrack:
        return await self._repo.upsert(user_id, track, learning_pace=pace.value)

    async def complete_onboarding(self, user_id: int, track: LearningTrack) -> UserTrack:
        return await self._repo.upsert(user_id, track, onboarding_completed=True, is_active=True)

    async def update_settings(self, user_id: int, track: LearningTrack, settings: dict) -> UserTrack:
        existing = await self.get_or_create(user_id, track)
        merged = {**(existing.settings or {}), **settings}
        return await self._repo.upsert(user_id, track, settings=merged)
