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

# Events for the level rework. State is already visible in the tables — what
# these add is movement: whether anything reaches "learned" now, what kind of
# answers people actually give, and whether the level we assign holds up. Each
# one exists to answer a question that was asked and couldn't be.
EVENT_ANSWER_GRADED = "answer_graded"  # every answer, with what it proved
# A constructor sentence or a topic-check answer. Word answers live in
# word_reviews; these had no dated record at all, so a day spent on grammar
# looked like a day off to everything that measures how much someone does.
EVENT_PHRASE_ANSWERED = "phrase_answered"
EVENT_WORD_MASTERED = "word_mastered"  # the outcome the rework was for
EVENT_PLACEMENT_COMPLETED = "placement_completed"  # what the test decides
EVENT_LEVEL_CHANGED = "level_changed"  # whether that decision survives contact
