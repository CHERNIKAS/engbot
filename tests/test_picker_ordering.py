"""Which signal decides what gets taught next, pinned at the query.

`selection_rank` is unit-tested, but nothing checked that the pickers actually
order by it — and for two years the repeat stream, which is ~60% of everything
pushed, ordered by due date alone. That is how an A1 learner was served
`frown`, `gaze` and `giggle` while 687 A1 words sat untouched: the intake query
filtered by level, the repeat query never did, and anything that got in stayed.

These assert the ORDER BY itself, because the bug was never in the ranking
function — it was in which query bothered to use it.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.domain.enums import LearningTrack
from app.infrastructure.repositories.user_words import UserWordRepository


class _Scalars:
    def all(self) -> list[Any]:
        return []

    def first(self) -> Any:
        return None


class _Result:
    def all(self) -> list[Any]:
        return []

    def first(self) -> Any:
        return None

    def scalars(self) -> _Scalars:
        return _Scalars()


class _RecordingSession:
    """Captures the statement instead of running it."""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return _Result()


def _order_by_sql(statement) -> str:
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    return sql[sql.index("ORDER BY"):]


async def _capture(method: str, **kwargs) -> str:
    session = _RecordingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await getattr(repo, method)(user_id=1, track=LearningTrack.ENGLISH, **kwargs)
    return _order_by_sql(session.statements[0])


@pytest.mark.asyncio
async def test_new_words_are_ordered_by_corpus_rank_not_the_guessed_bucket():
    """`freq_rank` was a 1-to-5 guess that put `salad` and `Friday` in the same
    bucket as `you` and `not`. It may still break ties for the ~900 words the
    corpus never saw, but it must not lead."""
    order = await _capture("pick_new_for_push", user_level="A1")
    assert "ngsl_rank" in order
    assert order.index("ngsl_rank") < order.index("freq_rank")


@pytest.mark.asyncio
async def test_new_words_prefer_the_users_own_choice_above_everything():
    """The one place the learner has said directly what they want."""
    order = await _capture("pick_new_for_push", user_level="A1")
    assert order.index("priority") < order.index("ngsl_rank")


@pytest.mark.asyncio
async def test_unambiguous_words_come_before_polysemous_ones():
    """`charge` and `stock` are frequent but a single translation teaches one
    sense as if it were the word, so they wait for the band's clearer words."""
    order = await _capture("pick_new_for_push", user_level="A1")
    assert order.index("polysemous") < order.index("freq_rank")


@pytest.mark.asyncio
async def test_repeats_lead_with_the_due_date():
    """Usefulness must never delay a word that is already due — a word repeated
    late is a word forgotten, which no ranking makes up for."""
    order = await _capture("pick_active_due", user_level="A1")
    assert order.index("next_review_at") < order.index("ngsl_rank")


@pytest.mark.asyncio
async def test_repeats_break_ties_by_fit_and_usefulness():
    """The regression this file exists for: after a gap, dozens fall due at
    once, and which of them the learner sees first stops being arbitrary."""
    order = await _capture("pick_active_due", user_level="A1")
    assert "ngsl_rank" in order
    assert "level" in order


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("pick_new_for_push", {"user_level": "A1"}),
        ("pick_active_due", {"user_level": "A1"}),
        ("pick_review_mastered", {}),
    ],
)
@pytest.mark.asyncio
async def test_no_picker_serves_a_word_form_as_its_own_word(method, kwargs):
    """«drove — вел машину» asks a learner to memorise a tense. The form is
    real knowledge and stays in the catalogue, but the irregular-verb and
    comparatives topics teach it — every picker has to agree on that, and one
    that forgot would quietly put `better` and `knew` back in rotation."""
    session = _RecordingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await getattr(repo, method)(user_id=1, track=LearningTrack.ENGLISH, **kwargs)
    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    where = sql[sql.index("WHERE"):sql.index("ORDER BY")]
    assert "is_inflection" in where
    assert "is_function_word" in where


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("pick_new_for_push", {"user_level": "A1"}),
        ("pick_active_due", {"user_level": "A1"}),
        ("pick_review_mastered", {}),
    ],
)
@pytest.mark.asyncio
async def test_phrases_are_kept_out_of_the_word_queue(method, kwargs):
    """A phrase has no corpus rank, and the ordering sends NULLs last — so
    leaving them in this queue parks all 102 of them behind two thousand ranked
    words. They get their own stream instead."""
    session = _RecordingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await getattr(repo, method)(user_id=1, track=LearningTrack.ENGLISH, **kwargs)
    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "is_phrase" in sql[sql.index("WHERE"):sql.index("ORDER BY")]


@pytest.mark.asyncio
async def test_phrases_come_in_the_order_the_phrasebook_teaches():
    """Greetings before the airport, the airport before the doctor. Nothing is
    randomised here: the pack order is already the teaching order, which is the
    whole reason this is not the word picker with a flag flipped."""
    session = _RecordingSession()
    repo = UserWordRepository(session)  # type: ignore[arg-type]
    await repo.pick_new_phrase(user_id=1, track=LearningTrack.ENGLISH)
    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    order = sql[sql.index("ORDER BY"):]
    assert "packs.id" in order
    assert order.index("packs.id") < order.index("pack_words.position")
    assert "is_phrase" in sql
