from __future__ import annotations

from typing import Any

from sqlalchemy.sql import Select

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.user_words import UserWordRepository


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        # quiz_distractors selects (translation, part_of_speech, level).
        # Plain-string rows mean "untagged" -> pos/level None.
        out = []
        for r in self._rows:
            if isinstance(r, tuple):
                out.append(r)
            else:
                out.append((r, None, None))
        return out


class QuizDistractorsFakeSession:
    """Returns different rows for the 'own user_words' query vs the 'pack_words'
    fallback query. We tell them apart by inspecting the FROM tables of the Select."""

    def __init__(self, own: list[Any], pack: list[Any]) -> None:
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
        own=["correct", "xxx", "yyy", "zzz"],
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
        own=["aaa"],
        pack=["aaa", "bbb", "ccc"],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=[],
    )
    assert sorted(distractors) == ["aaa", "bbb", "ccc"]


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


async def test_quiz_distractors_prefers_same_part_of_speech():
    """Given the answer is an A1 verb, verb distractors must outrank nouns/adjs."""
    session = QuizDistractorsFakeSession(
        own=[
            ("бежать", "verb", "A1"),
            ("стол", "noun", "A1"),
            ("красный", "adj", "A1"),
            ("идти", "verb", "A2"),
            ("прыгать", "verb", "B1"),
        ],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=["думать"],
        correct_pos="verb",
        correct_level="A1",
    )
    assert distractors == ["бежать", "идти", "прыгать"]  # all verbs, A1 first


async def test_quiz_distractors_drops_overlapping_meaning():
    """A distractor that shares a meaning word with the answer is never offered."""
    session = QuizDistractorsFakeSession(
        own=[
            ("хранить / держать", "verb", "A1"),  # overlaps the answer «держать»
            ("бежать", "verb", "A1"),
            ("прыгать", "verb", "A1"),
            ("идти", "verb", "A1"),
        ],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=["держать"],
        correct_pos="verb",
        correct_level="A1",
    )
    assert "хранить / держать" not in distractors
    assert len(distractors) == 3


async def test_negation_answer_prefers_negation_distractors():
    """A "не …" answer should be quizzed against other "не …" options, not nouns."""
    session = QuizDistractorsFakeSession(
        own=[
            ("не делаю", "verb", "A1"),
            ("не могу", "verb", "A1"),
            ("большой", "adj", "A1"),
            ("стол", "noun", "A1"),
            ("не буду", "verb", "A1"),
        ],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_user_word_id=42,
        limit=3, exclude_translations=["не имею"],
    )
    assert all(d.startswith("не ") for d in distractors), distractors
    assert "большой" not in distractors and "стол" not in distractors


async def test_non_negation_answer_avoids_negation_distractor():
    """A normal answer shouldn't get a lone "не …" option (also a giveaway)."""
    session = QuizDistractorsFakeSession(
        own=[
            ("большой", "adj", "A1"),
            ("маленький", "adj", "A1"),
            ("новый", "adj", "A1"),
            ("не имею", "verb", "A1"),
        ],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1, track=LearningTrack.ENGLISH, exclude_user_word_id=42,
        limit=3, exclude_translations=["красный"],
    )
    assert "не имею" not in distractors, distractors


async def test_quiz_distractors_meaning_guard_does_not_over_exclude():
    """Sharing letters but not a whole word must NOT be filtered (есть vs шесть)."""
    session = QuizDistractorsFakeSession(
        own=[("шесть", "noun", "A1"), ("семь", "noun", "A1"), ("восемь", "noun", "A1")],
        pack=[],
    )
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    distractors = await repo.quiz_distractors(
        user_id=1,
        track=LearningTrack.ENGLISH,
        exclude_user_word_id=42,
        limit=3,
        exclude_translations=["есть"],
    )
    assert sorted(distractors) == ["восемь", "семь", "шесть"]
