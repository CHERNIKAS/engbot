from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CategoryType, LearningTrack
from app.domain.models import Category, UserWord


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, category_id: int) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_by_name(
        self, user_id: int, track: LearningTrack, name: str
    ) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                Category.user_id == user_id,
                Category.track == track.value,
                Category.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int, track: LearningTrack) -> list[Category]:
        result = await self.session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.track == track.value,
                Category.type == CategoryType.USER.value,
            )
            .order_by(Category.name.asc())
        )
        return list(result.scalars().all())

    async def create(
        self, user_id: int, track: LearningTrack, name: str
    ) -> Category:
        category = Category(
            user_id=user_id,
            track=track.value,
            name=name,
            type=CategoryType.USER.value,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def rename(self, category_id: int, new_name: str) -> Category | None:
        category = await self.get(category_id)
        if category is None:
            return None
        category.name = new_name
        await self.session.flush()
        return category

    async def delete(self, category_id: int) -> None:
        category = await self.get(category_id)
        if category is None:
            return
        await self.session.delete(category)
        await self.session.flush()

    async def counts_for_user(
        self, user_id: int, track: LearningTrack
    ) -> dict[int | None, int]:
        result = await self.session.execute(
            select(UserWord.category_id, func.count(UserWord.id))
            .where(and_(UserWord.user_id == user_id, UserWord.track == track.value))
            .group_by(UserWord.category_id)
        )
        return {row[0]: row[1] for row in result.all()}
