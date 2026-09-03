from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import GrammarReview, WordReview


class WordReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        track: LearningTrack,
        user_word_id: int,
        session_id: int | None,
        result: str,
    ) -> WordReview:
        review = WordReview(
            user_id=user_id,
            track=track.value,
            user_word_id=user_word_id,
            session_id=session_id,
            result=result,
        )
        self.session.add(review)
        await self.session.flush()
        return review

    async def answers_per_active_day(
        self, user_id: int, track: LearningTrack, days: int = 14
    ) -> float | None:
        """Average answers on the days the user actually showed up, over the last
        `days`. None when there's no history yet.

        Averaged over *active* days rather than calendar days on purpose: this
        number sizes the active word pool, and a week off shouldn't shrink
        someone's pool to nothing and then starve them when they come back.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        per_day = (
            select(func.count(WordReview.id).label("c"))
            .where(
                WordReview.user_id == user_id,
                WordReview.track == track.value,
                WordReview.reviewed_at >= since,
            )
            .group_by(func.date_trunc("day", WordReview.reviewed_at))
            .subquery()
        )
        value = (await self.session.execute(select(func.avg(per_day.c.c)))).scalar()
        return float(value) if value is not None else None


class GrammarReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        track: LearningTrack,
        user_grammar_item_id: int,
        result: str,
    ) -> GrammarReview:
        review = GrammarReview(
            user_id=user_id,
            track=track.value,
            user_grammar_item_id=user_grammar_item_id,
            result=result,
        )
        self.session.add(review)
        await self.session.flush()
        return review
