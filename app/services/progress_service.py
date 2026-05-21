from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordStatus
from app.domain.models import User, WordReview
from app.infrastructure.repositories.user_words import UserWordRepository


@dataclass
class TrackProgress:
    track: LearningTrack
    studied_today: int
    daily_goal: int
    total_words: int
    mastered_words: int
    weak_words: int


@dataclass
class ProgressView:
    streak_days: int
    tracks: list[TrackProgress]


def _resolve_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_today(tz_name: str | None) -> date:
    tz = _resolve_tz(tz_name)
    return datetime.now(tz).date()


def _day_utc_bounds(local_day: date, tz_name: str | None) -> tuple[datetime, datetime]:
    """Returns [start_utc, end_utc) representing one calendar day in the user's TZ."""
    tz = _resolve_tz(tz_name)
    start_local = datetime.combine(local_day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


class ProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_words = UserWordRepository(session)

    async def track_view(
        self,
        user_id: int,
        track: LearningTrack,
        daily_goal: int,
        *,
        tz_name: str = "UTC",
    ) -> TrackProgress:
        studied_today = await self.studied_today_count(user_id, track, tz_name=tz_name)
        total = await self._user_words.total_for_user(user_id, track)
        mastered = await self._user_words.count_status(user_id, track, WordStatus.MASTERED)
        weak = await self._user_words.count_weak(user_id, track)
        return TrackProgress(
            track=track,
            studied_today=studied_today,
            daily_goal=daily_goal,
            total_words=total,
            mastered_words=mastered,
            weak_words=weak,
        )

    async def studied_today_count(
        self,
        user_id: int,
        track: LearningTrack,
        *,
        tz_name: str = "UTC",
    ) -> int:
        today_local = _local_today(tz_name)
        start_utc, end_utc = _day_utc_bounds(today_local, tz_name)
        q = select(func.count(WordReview.id)).where(
            and_(
                WordReview.user_id == user_id,
                WordReview.track == track.value,
                WordReview.reviewed_at >= start_utc,
                WordReview.reviewed_at < end_utc,
            )
        )
        return (await self._session.execute(q)).scalar_one() or 0

    async def update_streak(self, user: User) -> bool:
        """Global streak — shared across all tracks. Call when any track session finishes."""
        today_local = _local_today(user.timezone)
        if user.last_study_date == today_local:
            return False
        if user.last_study_date == today_local - timedelta(days=1):
            user.streak_days += 1
        else:
            user.streak_days = 1
        user.last_study_date = today_local
        await self._session.flush()
        return True
