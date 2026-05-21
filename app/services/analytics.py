from __future__ import annotations

from app.infrastructure.repositories.analytics import AnalyticsRepository
from app.logging_setup import get_logger

log = get_logger("analytics")


class Analytics:
    def __init__(self, repo: AnalyticsRepository) -> None:
        self._repo = repo

    async def emit(self, name: str, user_id: int | None, **props) -> None:
        try:
            await self._repo.emit(name=name, user_id=user_id, props=props)
        except Exception:  # noqa: BLE001
            log.exception("analytics_emit_failed", event=name, user_id=user_id)


EVENT_ONBOARDING_COMPLETED = "onboarding_completed"
EVENT_WORD_ADDED = "word_added"
EVENT_TXT_IMPORTED = "txt_imported"
EVENT_STUDY_STARTED = "study_started"
EVENT_STUDY_COMPLETED = "study_completed"
EVENT_STREAK_UPDATED = "streak_updated"
EVENT_PACK_ADDED = "pack_added"
