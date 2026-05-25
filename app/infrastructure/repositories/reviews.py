from __future__ import annotations

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
