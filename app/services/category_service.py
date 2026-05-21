from __future__ import annotations

from app.domain.enums import LearningTrack
from app.domain.models import Category
from app.infrastructure.repositories.categories import CategoryRepository

MAX_NAME_LEN = 64


class CategoryServiceError(Exception):
    pass


class CategoryService:
    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    async def list_user_categories(
        self, user_id: int, track: LearningTrack
    ) -> list[Category]:
        return await self._repo.list_for_user(user_id, track)

    async def create(self, user_id: int, track: LearningTrack, name: str) -> Category:
        clean = name.strip()
        if not clean:
            raise CategoryServiceError("empty")
        if len(clean) > MAX_NAME_LEN:
            raise CategoryServiceError("too_long")
        existing = await self._repo.get_by_name(user_id, track, clean)
        if existing is not None:
            raise CategoryServiceError("exists")
        return await self._repo.create(user_id=user_id, track=track, name=clean)

    async def get(self, category_id: int) -> Category | None:
        return await self._repo.get(category_id)

    async def delete(self, category_id: int) -> None:
        await self._repo.delete(category_id)

    async def counts(
        self, user_id: int, track: LearningTrack
    ) -> dict[int | None, int]:
        return await self._repo.counts_for_user(user_id, track)
