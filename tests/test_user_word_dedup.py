from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy.dialects.postgresql.dml import Insert as PgInsert

from app.domain.enums import LearningTrack, WordSource
from app.infrastructure.repositories.user_words import UserWordRepository


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    """Mimics just enough of AsyncSession for UserWordRepository.bulk_add."""

    def __init__(self, existing: list[Any] | None = None) -> None:
        # Keep a live reference so the test can append between bulk_add calls.
        self._existing = existing if existing is not None else []
        self.insert_calls: int = 0
        self.flush_count: int = 0

    async def execute(self, stmt: Any) -> FakeResult:
        if isinstance(stmt, PgInsert):
            self.insert_calls += 1
            return FakeResult([])
        return FakeResult(self._existing)

    async def flush(self) -> None:
        self.flush_count += 1


def _fake_uw(word_id: int, category_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=1, word_id=word_id, category_id=category_id, track="en"
    )


async def test_adds_each_new_word_exactly_once():
    session = FakeSession(existing=[])
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10, 20, 30],
        category_id=5,
        source=WordSource.MANUAL,
    )

    assert added == 3
    assert session.insert_calls == 1
    assert session.flush_count >= 1


async def test_existing_word_is_not_re_added_when_target_category_differs():
    """Word 10 already exists in category 1; user adds it again with category 2.
    Result: still ONE user_word row, no INSERT issued."""
    existing = [_fake_uw(word_id=10, category_id=1)]
    session = FakeSession(existing=existing)
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10],
        category_id=2,
        source=WordSource.MANUAL,
    )

    assert added == 0
    assert session.insert_calls == 0
    # Existing category not blindly overwritten — single folder semantic stays.
    assert existing[0].category_id == 1


async def test_existing_word_without_category_gets_assigned_one():
    existing = [_fake_uw(word_id=10, category_id=None)]
    session = FakeSession(existing=existing)
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10],
        category_id=7,
        source=WordSource.MANUAL,
    )

    assert added == 0
    assert session.insert_calls == 0
    assert existing[0].category_id == 7


async def test_mixed_existing_and_new_only_inserts_new():
    existing = [_fake_uw(word_id=10, category_id=1)]
    session = FakeSession(existing=existing)
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10, 20, 30],
        category_id=1,
        source=WordSource.MANUAL,
    )

    assert added == 2
    assert session.insert_calls == 1


async def test_empty_word_ids_returns_zero_no_inserts():
    session = FakeSession(existing=[])
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[],
        category_id=None,
        source=WordSource.MANUAL,
    )

    assert added == 0
    assert session.insert_calls == 0


async def test_idempotent_second_add_with_same_word_returns_zero():
    """Second add of the same word must be a no-op — guards the integration
    contract that one word = one user_word row."""
    existing: list[Any] = []
    session = FakeSession(existing=existing)
    repo = UserWordRepository(session)  # type: ignore[arg-type]

    added1 = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10],
        category_id=1,
        source=WordSource.MANUAL,
    )
    # Simulate the row landing in storage for the second call.
    existing.append(_fake_uw(word_id=10, category_id=1))

    added2 = await repo.bulk_add(
        user_id=1,
        track=LearningTrack.ENGLISH,
        word_ids=[10],
        category_id=2,
        source=WordSource.MANUAL,
    )

    assert added1 == 1
    assert added2 == 0
    assert existing[0].category_id == 1
