from __future__ import annotations

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CategoryType, LearningTrack
from app.domain.models import Category, UserWord


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, category_id: int, owner_id: int | None = None) -> Category | None:
        """Load a category by id. Pass `owner_id` to scope by owner — handlers
        acting on a client-supplied id MUST, or a forged callback can read or
        mutate another user's folder (returns None if it isn't theirs)."""
        cat = await self.session.get(Category, category_id)
        if cat is None or (owner_id is not None and cat.user_id != owner_id):
            return None
        return cat

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

    async def rename(
        self, category_id: int, new_name: str, owner_id: int | None = None
    ) -> Category | None:
        category = await self.get(category_id, owner_id=owner_id)
        if category is None:
            return None
        category.name = new_name
        await self.session.flush()
        return category

    async def delete(self, category_id: int, owner_id: int | None = None) -> None:
        category = await self.get(category_id, owner_id=owner_id)
        if category is None:
            return
        await self.session.delete(category)
        await self.session.flush()

    async def move_words(
        self,
        user_id: int,
        track: LearningTrack,
        from_category_id: int | None,
        to_category_id: int | None,
    ) -> int:
        """Reassign every word in one category to another (or to NULL).
        Returns how many words moved. No dedup needed: unique(user_id, word_id)
        means each word is a single row carrying exactly one category."""
        result = await self.session.execute(
            update(UserWord)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.category_id == from_category_id,
            )
            .values(category_id=to_category_id)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def counts_for_user(
        self, user_id: int, track: LearningTrack
    ) -> dict[int | None, int]:
        result = await self.session.execute(
            select(UserWord.category_id, func.count(UserWord.id))
            .where(and_(UserWord.user_id == user_id, UserWord.track == track.value))
            .group_by(UserWord.category_id)
        )
        return {row[0]: row[1] for row in result.all()}
