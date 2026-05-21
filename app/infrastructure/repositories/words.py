from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import Word


class WordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, word_id: int) -> Word | None:
        return await self.session.get(Word, word_id)

    async def get_by_normalized(self, track: LearningTrack, normalized: str) -> Word | None:
        result = await self.session.execute(
            select(Word).where(Word.track == track.value, Word.normalized_word == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_normalized_many(
        self, track: LearningTrack, normalized: Iterable[str]
    ) -> dict[str, Word]:
        keys = list({n for n in normalized if n})
        if not keys:
            return {}
        result = await self.session.execute(
            select(Word).where(Word.track == track.value, Word.normalized_word.in_(keys))
        )
        return {w.normalized_word: w for w in result.scalars().all()}

    async def upsert_many(self, track: LearningTrack, items: list[dict]) -> dict[str, Word]:
        """Insert words for the given track if missing. Returns normalized -> Word."""
        if not items:
            return {}

        rows = [{**item, "track": track.value} for item in items]
        stmt = (
            pg_insert(Word)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["track", "normalized_word"])
        )
        await self.session.execute(stmt)
        await self.session.flush()

        return await self.get_by_normalized_many(
            track, [i["normalized_word"] for i in rows]
        )

    async def update_example_if_empty(self, word_id: int, example: str) -> None:
        word = await self.get(word_id)
        if word is None or word.example_sentence:
            return
        word.example_sentence = example
        await self.session.flush()
