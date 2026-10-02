from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, literal_column, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import AnalyticsEvent, GrammarReview, WordReview


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
        response_ms: int | None = None,
        attempts: int | None = None,
    ) -> WordReview:
        review = WordReview(
            user_id=user_id,
            track=track.value,
            user_word_id=user_word_id,
            session_id=session_id,
            result=result,
            response_ms=response_ms,
            attempts=attempts,
        )
        self.session.add(review)
        await self.session.flush()
        return review

    async def typical_daily_answers(
        self, user_id: int, track: LearningTrack, days: int = 60
    ) -> float | None:
        """A representative "good day" for this user, in answers. None with no history.

        The 75th percentile of the days they actually showed up — not the mean,
        and not a short window. Both of those read a lull as a loss of capacity:
        over 14 days one prod user averaged 4.2 answers a day against 13.9
        across their whole history, and sizing their word pool on 4.2 would have
        starved them for as long as the slump lasted. Capacity is better
        described by someone's good days than by their average one.

        Days with no answers are excluded, so time off shrinks nothing.

        Every answer counts — word cards, constructor sentences and topic-check
        answers alike. Counting only words read a day spent on grammar as a day
        off, and sized that learner's pool (and their new words) for someone
        who barely studies.
        """
        from app.services.analytics import EVENT_PHRASE_ANSWERED

        since = datetime.now(timezone.utc) - timedelta(days=days)
        answers = union_all(
            select(WordReview.reviewed_at.label("at")).where(
                WordReview.user_id == user_id,
                WordReview.track == track.value,
                WordReview.reviewed_at >= since,
            ),
            select(AnalyticsEvent.created_at.label("at")).where(
                AnalyticsEvent.user_id == user_id,
                AnalyticsEvent.name == EVENT_PHRASE_ANSWERED,
                AnalyticsEvent.created_at >= since,
            ),
        ).subquery()
        per_day = (
            select(func.count(literal_column("1")).label("c"))
            .select_from(answers)
            .group_by(func.date_trunc("day", answers.c.at))
            .subquery()
        )
        value = (
            await self.session.execute(
                select(func.percentile_cont(0.75).within_group(per_day.c.c.asc()))
            )
        ).scalar()
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
        response_ms: int | None = None,
        attempts: int | None = None,
    ) -> GrammarReview:
        review = GrammarReview(
            user_id=user_id,
            track=track.value,
            user_grammar_item_id=user_grammar_item_id,
            result=result,
            response_ms=response_ms,
            attempts=attempts,
        )
        self.session.add(review)
        await self.session.flush()
        return review
