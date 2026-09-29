"""Abandoning a card has to mean something on the next turn.

`PUSH_MAX_ATTEMPTS = 3` reads like a limit and was not one. A card dropped after
three nudges left no trace anywhere the pickers look, so the very next turn
chose the same card and started another round of three — the counter reset
rather than the card retiring.

Production, 29 September: one learner received a single constructor phrase six
times in twenty-one hours, each time logged as a fresh card, up to 24 messages
about one sentence. Word cards were fine — `state["last"]` already excluded the
last one — which is why this went unnoticed for the types that had no such
guard.

Every test here checks the *second* pass. The first pass always looked correct;
that is exactly why nothing caught it.
"""
from __future__ import annotations

import pytest

from app.infrastructure.repositories.constructor import RECENT_MEMORY


class _Row:
    def __init__(self, recent=None, score=0.4, answered=3):
        self.recent = list(recent or [])
        self.score = score
        self.answered = answered
        self.test_due_at = None


class _Repo:
    """Just enough of ConstructorRepository to drive the two new methods."""

    def __init__(self, row):
        self.row = row
        self.flushed = 0

    async def ensure_state(self, user_id, topic_id):
        return self.row

    async def flush(self):
        self.flushed += 1


def _bind(method_name, repo):
    from app.infrastructure.repositories.constructor import ConstructorRepository

    service = ConstructorRepository.__new__(ConstructorRepository)
    service.session = repo
    service.ensure_state = repo.ensure_state
    return getattr(service, method_name)


@pytest.mark.asyncio
async def test_an_ignored_phrase_is_not_chosen_again():
    """The whole bug in one assertion: after abandoning, the phrase is in the
    recency list that `pick_phrase` consults."""
    row = _Row()
    repo = _Repo(row)
    await _bind("note_shown", repo)(user_id=1, topic_id=2, phrase_id=42)
    assert 42 in row.recent


@pytest.mark.asyncio
async def test_ignoring_a_phrase_is_not_a_wrong_answer():
    """An ignore is «not now». Scoring it would let a silent evening drag a
    topic's mark down and push it back to the blocks mode."""
    row = _Row(score=0.62, answered=7)
    repo = _Repo(row)
    await _bind("note_shown", repo)(user_id=1, topic_id=2, phrase_id=42)
    assert row.score == 0.62
    assert row.answered == 7


@pytest.mark.asyncio
async def test_the_recency_list_stays_bounded():
    """It is written on every abandon now, not just on answers, so an inactive
    learner must not grow it without limit."""
    row = _Row(recent=list(range(100)))
    repo = _Repo(row)
    await _bind("note_shown", repo)(user_id=1, topic_id=2, phrase_id=999)
    assert len(row.recent) == RECENT_MEMORY
    assert row.recent[-1] == 999


@pytest.mark.asyncio
async def test_an_ignored_check_moves_out_of_today():
    """`due_test_topic` selects on `test_due_at <= now`, so an ignored offer
    with the date left alone is re-offered on the next turn — and «at most one
    check a day» silently stops holding."""
    from datetime import datetime, timezone

    row = _Row()
    repo = _Repo(row)
    await _bind("defer_test", repo)(user_id=1, topic_id=2)
    assert row.test_due_at is not None
    assert row.test_due_at > datetime.now(timezone.utc)
