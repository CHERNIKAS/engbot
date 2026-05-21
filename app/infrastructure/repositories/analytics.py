from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AnalyticsEvent


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(self, name: str, user_id: int | None, props: dict | None = None) -> None:
        event = AnalyticsEvent(name=name, user_id=user_id, props=props or {})
        self.session.add(event)
        await self.session.flush()
