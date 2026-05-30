"""Reverse cards (RU prompt → pick the English word) need English-writing
distractors. reverse_distractors mirrors quiz_distractors: own vocab first,
pack fallback on cold start, same-POS/level ranked first."""
from __future__ import annotations

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.user_words import UserWordRepository
from tests.test_quiz_cold_start import QuizDistractorsFakeSession


async def test_reverse_uses_own_writings_when_enough():
    session = QuizDistractorsFakeSession(
        own=["cat", "dog", "house", "run"],
        pack=["SHOULD_NOT_USE"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    out = await repo.reverse_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_word_id=42, limit=3
    )
    assert len(out) == 3
    assert "SHOULD_NOT_USE" not in out
    assert "pack" not in session.queries


async def test_reverse_falls_back_to_packs_on_cold_start():
    session = QuizDistractorsFakeSession(
        own=["mine"],
        pack=["alpha", "beta", "gamma", "delta"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    out = await repo.reverse_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_word_id=42, limit=3
    )
    assert len(out) == 3
    assert "pack" in session.queries


async def test_reverse_prefers_same_part_of_speech():
    """An A1 verb answer → verb writings outrank nouns/adjs."""
    session = QuizDistractorsFakeSession(
        own=[
            ("run", "verb", "A1"),
            ("table", "noun", "A1"),
            ("red", "adj", "A1"),
            ("walk", "verb", "A2"),
            ("jump", "verb", "B1"),
        ],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    out = await repo.reverse_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_word_id=42, limit=3,
        correct_pos="verb", correct_level="A1",
    )
    assert out == ["run", "walk", "jump"]  # all verbs, A1 first


async def test_reverse_dedupes_across_sources():
    session = QuizDistractorsFakeSession(
        own=["cat"],
        pack=["cat", "dog", "fish"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    out = await repo.reverse_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_word_id=42, limit=3
    )
    assert sorted(out) == ["cat", "dog", "fish"]


async def test_reverse_empty_returns_empty():
    session = QuizDistractorsFakeSession(own=[], pack=[])
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    out = await repo.reverse_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_word_id=42, limit=3
    )
    assert out == []
