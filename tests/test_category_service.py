from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.enums import LearningTrack
from app.services.category_service import CategoryService, CategoryServiceError

TRACK = LearningTrack.ENGLISH


class FakeCatRepo:
    def __init__(self, existing_by_name: dict | None = None) -> None:
        self._existing = existing_by_name or {}
        self.renamed: tuple[int, str] | None = None
        self.move_calls: list[tuple] = []
        self.deleted: list[int] = []

    async def get_by_name(self, user_id, track, name):
        return self._existing.get(name)

    async def rename(self, category_id, new_name, owner_id=None):
        self.renamed = (category_id, new_name)
        return SimpleNamespace(id=category_id, name=new_name)

    async def move_words(self, user_id, track, from_id, to_id):
        self.move_calls.append((from_id, to_id))
        return 7

    async def delete(self, category_id, owner_id=None):
        self.deleted.append(category_id)


def _svc(repo: FakeCatRepo) -> CategoryService:
    return CategoryService(repo)  # type: ignore[arg-type]


async def test_rename_empty_raises():
    with pytest.raises(CategoryServiceError) as e:
        await _svc(FakeCatRepo()).rename(1, TRACK, 5, "   ")
    assert str(e.value) == "empty"


async def test_rename_too_long_raises():
    with pytest.raises(CategoryServiceError) as e:
        await _svc(FakeCatRepo()).rename(1, TRACK, 5, "x" * 65)
    assert str(e.value) == "too_long"


async def test_rename_duplicate_other_category_raises():
    repo = FakeCatRepo(existing_by_name={"Work": SimpleNamespace(id=99)})
    with pytest.raises(CategoryServiceError) as e:
        await _svc(repo).rename(1, TRACK, 5, "Work")
    assert str(e.value) == "exists"


async def test_rename_same_name_same_category_ok():
    repo = FakeCatRepo(existing_by_name={"Work": SimpleNamespace(id=5)})
    cat = await _svc(repo).rename(1, TRACK, 5, "Work")
    assert cat.name == "Work"
    assert repo.renamed == (5, "Work")


async def test_rename_ok_calls_repo():
    repo = FakeCatRepo()
    cat = await _svc(repo).rename(1, TRACK, 5, "  Travel  ")
    assert cat.name == "Travel"
    assert repo.renamed == (5, "Travel")


async def test_move_words_delegates():
    repo = FakeCatRepo()
    moved = await _svc(repo).move_words(1, TRACK, 5, None)
    assert moved == 7
    assert repo.move_calls == [(5, None)]


async def test_merge_moves_then_deletes_source():
    repo = FakeCatRepo()
    moved = await _svc(repo).merge(1, TRACK, source_id=5, target_id=8)
    assert moved == 7
    assert repo.move_calls == [(5, 8)]
    assert repo.deleted == [5]
