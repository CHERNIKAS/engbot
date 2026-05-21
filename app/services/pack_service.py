from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import LearningTrack, WordSource
from app.domain.models import Pack
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_words import UserWordRepository


@dataclass
class PackAddResult:
    added: int


class PackService:
    def __init__(
        self,
        pack_repo: PackRepository,
        user_word_repo: UserWordRepository,
    ) -> None:
        self._packs = pack_repo
        self._user_words = user_word_repo

    async def list_categories(self, track: LearningTrack) -> list[str]:
        return await self._packs.list_categories(track)

    async def list_for_categories(
        self, track: LearningTrack, categories: list[str]
    ) -> list[Pack]:
        return await self._packs.list_by_categories(track, categories)

    async def preview(self, pack_id: int) -> Pack | None:
        return await self._packs.get(pack_id)

    async def add_pack(
        self,
        user_id: int,
        track: LearningTrack,
        pack_id: int,
        category_id: int | None,
    ) -> PackAddResult:
        word_ids = await self._packs.get_pack_word_ids(pack_id)
        added = await self._user_words.bulk_add(
            user_id=user_id,
            track=track,
            word_ids=word_ids,
            category_id=category_id,
            source=WordSource.PACK,
        )
        return PackAddResult(added=added)
