from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import Pack, PackWord, Word


class PackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, track: LearningTrack) -> list[Pack]:
        result = await self.session.execute(
            select(Pack)
            .where(Pack.is_active.is_(True), Pack.track == track.value)
            .order_by(Pack.category.asc(), Pack.title.asc())
        )
        return list(result.scalars().all())

    async def list_categories(self, track: LearningTrack) -> list[str]:
        result = await self.session.execute(
            select(Pack.category)
            .where(Pack.is_active.is_(True), Pack.track == track.value)
            .distinct()
            .order_by(Pack.category.asc())
        )
        return [r[0] for r in result.all()]

    async def get(self, pack_id: int) -> Pack | None:
        return await self.session.get(Pack, pack_id)

    async def list_by_categories(
        self, track: LearningTrack, categories: list[str]
    ) -> list[Pack]:
        if not categories:
            return await self.list_active(track)
        result = await self.session.execute(
            select(Pack)
            .where(
                Pack.is_active.is_(True),
                Pack.track == track.value,
                Pack.category.in_(categories),
            )
            .order_by(Pack.category.asc(), Pack.title.asc())
        )
        return list(result.scalars().all())

    async def get_pack_words(self, pack_id: int) -> list[Word]:
        result = await self.session.execute(
            select(Word)
            .join(PackWord, PackWord.word_id == Word.id)
            .where(PackWord.pack_id == pack_id)
            .order_by(PackWord.position.asc())
        )
        return list(result.scalars().all())

    async def get_pack_word_ids(self, pack_id: int) -> list[int]:
        result = await self.session.execute(
            select(PackWord.word_id).where(PackWord.pack_id == pack_id).order_by(PackWord.position.asc())
        )
        return [r[0] for r in result.all()]
