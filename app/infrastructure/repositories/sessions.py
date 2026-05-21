from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import StudySession


class StudySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        track: LearningTrack,
        mode: str,
        scope: str,
        scope_ref_id: int | None,
        words_total: int,
    ) -> StudySession:
        session = StudySession(
            user_id=user_id,
            track=track.value,
            mode=mode,
            scope=scope,
            scope_ref_id=scope_ref_id,
            words_total=words_total,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get(self, session_id: int) -> StudySession | None:
        return await self.session.get(StudySession, session_id)

    async def finish(self, session_id: int, correct: int, wrong: int) -> None:
        s = await self.get(session_id)
        if s is None:
            return
        s.finished_at = datetime.now(timezone.utc)
        s.correct_count = correct
        s.wrong_count = wrong
        await self.session.flush()

    async def increment_counters(self, session_id: int, correct_delta: int, wrong_delta: int) -> None:
        s = await self.get(session_id)
        if s is None:
            return
        s.correct_count += correct_delta
        s.wrong_count += wrong_delta
        await self.session.flush()
