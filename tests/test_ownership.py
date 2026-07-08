"""Ownership scoping: a forged id must not touch another user's rows.

These exercise the repository-level owner filter that every id-taking handler
now passes. The fake session models get() by primary key so the owner check
runs against the real row.owner_id."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.user_words import UserWordRepository


class FakeSession:
    def __init__(self, rows: dict):
        self._rows = rows          # {(Model, id): obj}
        self.deleted: list = []

    async def get(self, model, pk):
        return self._rows.get((model.__name__, pk))

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass


def _uw(uw_id: int, user_id: int):
    from app.domain.models import UserWord
    obj = SimpleNamespace(id=uw_id, user_id=user_id, archived=False, snooze_until=None)
    return ("UserWord", uw_id), obj


def _cat(cat_id: int, user_id: int):
    from app.domain.models import Category
    obj = SimpleNamespace(id=cat_id, user_id=user_id, name="folder")
    return ("Category", cat_id), obj


async def test_userword_get_rejects_foreign_owner():
    (_k, victim), = [ _uw(5, user_id=1) ]
    session = FakeSession(dict([_uw(5, user_id=1)]))
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    assert await repo.get(5, owner_id=1) is not None       # owner sees it
    assert await repo.get(5, owner_id=2) is None           # attacker does not
    assert await repo.get(5) is not None                   # unscoped internal use still works


async def test_userword_delete_scoped_by_owner():
    session = FakeSession(dict([_uw(5, user_id=1)]))
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await repo.delete(5, owner_id=2)                        # attacker
    assert session.deleted == []                           # nothing deleted
    await repo.delete(5, owner_id=1)                        # owner
    assert len(session.deleted) == 1


async def test_category_get_rejects_foreign_owner():
    session = FakeSession(dict([_cat(9, user_id=1)]))
    repo = CategoryRepository(session)  # type: ignore[arg-type]
    assert await repo.get(9, owner_id=1) is not None
    assert await repo.get(9, owner_id=2) is None


async def test_category_delete_and_rename_scoped_by_owner():
    session = FakeSession(dict([_cat(9, user_id=1)]))
    repo = CategoryRepository(session)  # type: ignore[arg-type]
    await repo.delete(9, owner_id=2)
    assert session.deleted == []
    renamed = await repo.rename(9, "hacked", owner_id=2)
    assert renamed is None
    ok = await repo.rename(9, "mine", owner_id=1)
    assert ok is not None and ok.name == "mine"
