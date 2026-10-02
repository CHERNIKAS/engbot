from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import DayPlan


class DayPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def open_plan(self, user_id: int, track: LearningTrack) -> DayPlan | None:
        """The plan currently in flight, or None.

        There is at most one — a partial unique index enforces it — because
        "yesterday's plan is today's plan" has no meaning with two of them.
        """
        q = select(DayPlan).where(
            DayPlan.user_id == user_id,
            DayPlan.track == track.value,
            DayPlan.closed_at.is_(None),
        )
        return (await self.session.execute(q)).scalars().first()

    async def closed_on(self, user_id: int, track: LearningTrack, day: date) -> bool:
        """Whether the plan made for `day` is already finished."""
        q = (
            select(DayPlan.id)
            .where(
                DayPlan.user_id == user_id,
                DayPlan.track == track.value,
                DayPlan.opened_on == day,
                DayPlan.closed_at.isnot(None),
            )
            .limit(1)
        )
        return (await self.session.execute(q)).first() is not None

    async def create(
        self, user_id: int, track: LearningTrack, size: int, items: list[dict], opened_on: date
    ) -> DayPlan:
        plan = DayPlan(
            user_id=user_id,
            track=track.value,
            size=size,
            items=items,
            opened_on=opened_on,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def save_items(self, plan_id: int, items: list[dict]) -> None:
        """Rewrite the item list.

        JSONB is replaced wholesale rather than patched in place: SQLAlchemy
        does not track mutations inside a JSON column, so appending to
        `plan.items` and flushing would silently write nothing.
        """
        await self.session.execute(
            update(DayPlan).where(DayPlan.id == plan_id).values(items=items)
        )
        await self.session.flush()

    async def close(self, plan_id: int, now: datetime | None = None) -> None:
        await self.session.execute(
            update(DayPlan)
            .where(DayPlan.id == plan_id, DayPlan.closed_at.is_(None))
            .values(closed_at=now or datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def recent_closed(
        self, user_id: int, track: LearningTrack, limit: int = 14
    ) -> list[DayPlan]:
        """Most recent finished plans, newest first — the history the resize
        rule reads. Counted from rows rather than from a running counter so a
        missed write cannot leave the size drifting forever."""
        q = (
            select(DayPlan)
            .where(
                DayPlan.user_id == user_id,
                DayPlan.track == track.value,
                DayPlan.closed_at.isnot(None),
            )
            .order_by(DayPlan.opened_on.desc())
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def last_size(self, user_id: int, track: LearningTrack) -> int | None:
        """Size of the most recent plan, open or closed."""
        q = (
            select(DayPlan.size)
            .where(DayPlan.user_id == user_id, DayPlan.track == track.value)
            .order_by(DayPlan.opened_on.desc(), DayPlan.id.desc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalar()

    async def closed_on_days(
        self, user_id: int, track: LearningTrack, limit: int = 30
    ) -> list[date]:
        """Push days that ended with a closed plan, newest first.

        A plan held across several days closes once, on the day it was opened,
        so this is "days the learner finished what was asked" rather than "days
        they answered something".
        """
        q = (
            select(DayPlan.opened_on)
            .where(
                DayPlan.user_id == user_id,
                DayPlan.track == track.value,
                DayPlan.closed_at.isnot(None),
            )
            .order_by(DayPlan.opened_on.desc())
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def count_open(self, user_id: int) -> int:
        q = select(func.count(DayPlan.id)).where(
            DayPlan.user_id == user_id, DayPlan.closed_at.is_(None)
        )
        return (await self.session.execute(q)).scalar_one()
