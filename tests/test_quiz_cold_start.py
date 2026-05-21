from __future__ import annotations

from typing import Any

from sqlalchemy.sql import Select

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.user_words import UserWordRepository


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return [(r,) for r in self._rows]


class QuizDistractorsFakeSession:
    """Returns different rows for the 'own user_words' query vs the 'pack_words'
    fallback query. We tell them apart by inspecting the FROM tables of the Select."""

    def __init__(self, own: list[str], pack: list[str]) -> None:
        self._own = own
        self._pack = pack
        self.queries: list[str] = []

    async def execute(self, stmt: Select) -> FakeResult:
        src_repr = str(stmt)
        if "pack_words" in src_repr:
            self.queries.append("pack")
            return FakeResult(self._pack)
        self.queries.append("own")
        return FakeResult(self._own)


async def test_quiz_distractors_uses_own_translations_when_enough():
    """With ≥3 own translations, we never reach the pack fallback."""
    session = QuizDistractorsFakeSession(
        own=["перевод1", "перевод2", "перевод3", "перевод4"],
        pack=["должно_не_использоваться"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=[],
    )
    assert len(distractors) == 3
    assert all(d.startswith("перевод") for d in distractors)
    assert "pack" not in session.queries  # cold-start path NOT used


async def test_quiz_distractors_falls_back_to_packs_for_cold_start():
    """User has only 1 own translated word — must top up from pack translations."""
    session = QuizDistractorsFakeSession(
        own=["один_свой"],
        pack=["pack_a", "pack_b", "pack_c", "pack_d"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=[],
    )
    assert len(distractors) == 3
    assert "один_свой" in distractors
    pack_used = [d for d in distractors if d.startswith("pack_")]
    assert len(pack_used) == 2
    assert "pack" in session.queries


async def test_quiz_distractors_excludes_correct_answer():
    session = QuizDistractorsFakeSession(
        own=["correct", "x", "y", "z"],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=["correct"],
    )
    assert "correct" not in distractors
    assert len(distractors) == 3


async def test_quiz_distractors_deduplicates_across_sources():
    """If a word appears both in user vocab and packs, only counted once."""
    session = QuizDistractorsFakeSession(
        own=["a"],
        pack=["a", "b", "c"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=[],
    )
    assert sorted(distractors) == ["a", "b", "c"]


async def test_quiz_distractors_with_no_data_at_all_returns_empty():
    session = QuizDistractorsFakeSession(own=[], pack=[])
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=[],
    )
    assert distractors == []
