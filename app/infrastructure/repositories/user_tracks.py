from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import UserTrack


class UserTrackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, track: LearningTrack) -> UserTrack | None:
        result = await self.session.execute(
            select(UserTrack).where(
                UserTrack.user_id == user_id, UserTrack.track == track.value
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, user_id: int) -> list[UserTrack]:
        result = await self.session.execute(
            select(UserTrack)
            .where(UserTrack.user_id == user_id, UserTrack.is_active.is_(True))
            .order_by(UserTrack.track.asc())
        )
        return list(result.scalars().all())

    async def list_all(self, user_id: int) -> list[UserTrack]:
        result = await self.session.execute(
            select(UserTrack).where(UserTrack.user_id == user_id).order_by(UserTrack.track.asc())
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: int,
        track: LearningTrack,
        *,
        daily_goal_words: int | None = None,
        learning_pace: str | None = None,
        is_active: bool | None = None,
        onboarding_completed: bool | None = None,
        settings: dict | None = None,
    ) -> UserTrack:
        values: dict = {"user_id": user_id, "track": track.value}
        if daily_goal_words is not None:
            values["daily_goal_words"] = daily_goal_words
        if learning_pace is not None:
            values["learning_pace"] = learning_pace
        if is_active is not None:
            values["is_active"] = is_active
        if onboarding_completed is not None:
            values["onboarding_completed"] = onboarding_completed
        if settings is not None:
            values["settings"] = settings

        update_set = {k: v for k, v in values.items() if k not in ("user_id", "track")}
        stmt = pg_insert(UserTrack).values(values)
        if update_set:
            stmt = stmt.on_conflict_do_update(index_elements=["user_id", "track"], set_=update_set)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "track"])
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(user_id, track)  # type: ignore[return-value]

    async def set_active(self, user_id: int, track: LearningTrack, active: bool) -> None:
        ut = await self.get(user_id, track)
        if ut is None:
            if active:
                await self.upsert(user_id, track, is_active=True)
            return
        ut.is_active = active
        await self.session.flush()
