"""The review stream only serves mastered words that are actually due.

pick_review_mastered used to draw by weighted random over every mastered word
and never looked at next_review_at. With all scores at 5.0 the weights were
equal, so a word answered minutes ago with a 23-day interval was as likely as
one a month overdue: prod had `desk` back three times inside 24 hours.

There is no database in the test suite, so this pins the query itself.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.dialects import postgresql

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.user_words import UserWordRepository


class _Result:
    def all(self) -> list[Any]:
        return []


class _CapturingSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> _Result:
        self.statements.append(stmt)
        return _Result()


async def _sql() -> str:
    session = _CapturingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await repo.pick_review_mastered(1, LearningTrack.ENGLISH)
    assert len(session.statements) == 1
    return str(session.statements[0].compile(dialect=postgresql.dialect())).lower()


async def test_only_words_past_their_due_date_are_eligible():
    assert "user_words.next_review_at <=" in await _sql()


async def test_the_most_overdue_word_comes_first():
    sql = await _sql()
    order = sql.split("order by", 1)[1]
    assert order.strip().startswith("user_words.next_review_at asc")


async def test_the_draw_is_no_longer_random():
    """Randomness is what let a just-reviewed word come straight back."""
    assert "random()" not in await _sql()


async def test_nothing_due_means_no_pick():
    session = _CapturingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    assert await repo.pick_review_mastered(1, LearningTrack.ENGLISH) is None
