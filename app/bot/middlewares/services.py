from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.analytics import AnalyticsRepository
from app.infrastructure.repositories.user_tracks import UserTrackRepository
from app.services.analytics import Analytics
from app.services.answer_check import AnswerCheckService
from app.services.study_session_service import StudySessionService
from app.services.track_context_service import TrackContextService
from app.services.user_track_service import UserTrackService


class ServicesMiddleware(BaseMiddleware):
    """Builds per-update services and resolves the user's current learning track."""

    def __init__(self, redis: Redis, track_context: TrackContextService) -> None:
        self._redis = redis
        self._track_context = track_context

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        user = data.get("user")

        data.setdefault("redis", self._redis)
        data["track_context"] = self._track_context

        if user is not None:
            current_track = await self._track_context.get(user.id)
            data["current_track"] = current_track

            if session is not None:
                track_repo = UserTrackRepository(session)
                track_service = UserTrackService(track_repo)
                data["user_track_service"] = track_service
                # Make sure the row exists for the current track — handlers can rely on it.
                user_track = await track_service.get_or_create(user.id, current_track)
                data["user_track"] = user_track
        else:
            data["current_track"] = LearningTrack.ENGLISH

        if session is not None:
            data["analytics"] = Analytics(AnalyticsRepository(session))
            data["study_session"] = StudySessionService(session, self._redis)
        data["answer_check"] = AnswerCheckService(self._redis)

        return await handler(event, data)
