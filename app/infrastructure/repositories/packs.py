from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordStatus
from app.domain.models import Pack, PackWord, UserWord, Word


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

    async def stats_for_user(
        self, user_id: int, track: LearningTrack
    ) -> dict[int, tuple[int, int]]:
        """Per-pack (owned, mastered) counts for one user — one query, no N+1."""
        q = (
            select(
                PackWord.pack_id,
                func.count(UserWord.id),
                func.count(UserWord.id).filter(
                    UserWord.status == WordStatus.MASTERED.value
                ),
            )
            .join(
                UserWord,
                and_(
                    UserWord.word_id == PackWord.word_id,
                    UserWord.user_id == user_id,
                    UserWord.track == track.value,
                ),
            )
            .group_by(PackWord.pack_id)
        )
        rows = (await self.session.execute(q)).all()
        return {int(r[0]): (int(r[1]), int(r[2])) for r in rows}
