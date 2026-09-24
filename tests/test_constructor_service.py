"""Driving one exercise end to end, against fakes for the database.

The service is the seam where the pure card logic meets stored progress, so
what is worth testing here is the wiring: that both modes are graded against
the same expectation, that a finished card stops asking for taps, and that the
mode switch and the pass are written exactly when the rules say.
"""
from __future__ import annotations

import pytest

from app.domain import constructor as c
from app.services.constructor_service import ConstructorService

SLOTS = [
    {"correct": "She", "options": ["She", "They", "I"]},
    {"correct": "doesn't", "options": ["doesn't", "don't", "didn't"]},
    {"correct": "live here.", "options": ["live here.", "lives here."]},
]


class _Phrase:
    id = 7
    ru = "Она не живет здесь."
    en = "She doesn't live here."
    alternatives = ["She does not live here."]
    slots = SLOTS


class _Topic:
    id = 3
    title = "Present Simple"


class _Row:
    def __init__(self, score=0.0, typing=False, answered=0, passed_at=None):
        self.score = score
        self.typing = typing
        self.answered = answered
        self.passed_at = passed_at
        self.recent = []


class _Repo:
    def __init__(self, row=None):
        self.row = row or _Row()
        self.recorded = None

    async def state(self, user_id, topic_id):
        return self.row

    async def ensure_state(self, user_id, topic_id):
        return self.row

    async def record_answer(self, **kwargs):
        self.recorded = kwargs
        return self.row


def _service(row=None):
    service = ConstructorService.__new__(ConstructorService)
    service._repo = _Repo(row)
    return service


@pytest.mark.asyncio
async def test_a_completed_sentence_stops_asking_for_taps():
    """A card that kept offering options after the last slot would be
    unanswerable — there is nothing left to choose."""
    service = _service()
    state = c.CardState(chosen=("She", "doesn't"))
    new_state, view = await service.tap_slot(1, _Phrase(), _Topic(), state, 0)
    assert view is None
    assert c.is_complete(SLOTS, list(new_state.chosen))


@pytest.mark.asyncio
async def test_running_out_of_attempts_ends_the_card():
    """Otherwise a learner tapping wrong forever holds the plan open on one
    sentence."""
    service = _service()
    state = c.CardState(attempt=c.MAX_ATTEMPTS)
    _, view = await service.tap_slot(1, _Phrase(), _Topic(), state, 1)  # wrong
    assert view is None


@pytest.mark.asyncio
async def test_a_wrong_tap_re_renders_with_the_same_slot_open():
    service = _service()
    _, view = await service.tap_slot(1, _Phrase(), _Topic(), c.CardState(), 1)
    assert view is not None
    assert view.options == SLOTS[0]["options"]


@pytest.mark.asyncio
async def test_undo_brings_back_the_previous_slot():
    service = _service()
    state = c.CardState(chosen=("She",))
    new_state, view = await service.undo(1, _Phrase(), _Topic(), state)
    assert new_state.chosen == ()
    assert view.options == SLOTS[0]["options"]
    assert view.can_undo is False


@pytest.mark.asyncio
async def test_a_hint_in_the_assisted_mode_places_the_piece():
    """With the options already on screen there is nothing else to reveal, so
    the help has to be the answer itself."""
    service = _service()
    new_state, view = await service.hint(1, _Phrase(), _Topic(), c.CardState())
    assert new_state.chosen == ("She",)
    assert new_state.hinted
    assert view.options == SLOTS[1]["options"]


@pytest.mark.asyncio
async def test_a_hint_in_the_typing_mode_reveals_the_opening():
    service = _service(_Row(typing=True))
    _, view = await service.hint(1, _Phrase(), _Topic(), c.CardState(typing=True))
    assert "She doesn&#x27;t" in view.text
    assert view.options == []


@pytest.mark.asyncio
async def test_both_modes_are_graded_against_the_same_expectation():
    """If they drifted, the assisted mode would walk the learner to an answer
    the typing mode rejects — and it would read as the learner's mistake."""
    service = _service()
    assembled = await service.settle(1, _Phrase(), _Topic(), c.CardState(chosen=tuple(
        s["correct"] for s in SLOTS
    )))
    typed = await service.settle(1, _Phrase(), _Topic(), c.CardState(typing=True), answer=_Phrase.en)
    assert assembled.correct and typed.correct


@pytest.mark.asyncio
async def test_a_spelled_out_alternative_is_accepted():
    service = _service(_Row(typing=True))
    result = await service.settle(
        1, _Phrase(), _Topic(), c.CardState(typing=True), answer="She does not live here."
    )
    assert result.correct


@pytest.mark.asyncio
async def test_a_miss_scores_nothing_but_still_moves_the_topic():
    """The score has to fall on bad answers, or it could only ever climb."""
    service = _service(_Row(score=0.9))
    result = await service.settle(
        1, _Phrase(), _Topic(), c.CardState(typing=True), answer="She don't live here."
    )
    assert not result.correct
    assert result.answer_credit == 0.0
    assert result.score_after < result.score_before


@pytest.mark.asyncio
async def test_the_mode_switch_is_written_when_the_score_crosses():
    service = _service(_Row(score=c.TO_TYPING, answered=30))
    result = await service.settle(1, _Phrase(), _Topic(), c.CardState(chosen=tuple(
        s["correct"] for s in SLOTS
    )))
    assert result.switched_to_typing
    assert service._repo.recorded["typing"] is True


@pytest.mark.asyncio
async def test_a_topic_is_never_passed_from_the_assisted_mode_alone():
    """Even a perfect score there proves recognition, not production."""
    service = _service(_Row(score=0.99, typing=False, answered=5))
    result = await service.settle(1, _Phrase(), _Topic(), c.CardState(chosen=tuple(
        s["correct"] for s in SLOTS
    )))
    assert not result.passed


@pytest.mark.asyncio
async def test_a_typed_topic_at_full_marks_passes():
    service = _service(_Row(score=0.99, typing=True, answered=c.MIN_ANSWERS_TO_PASS))
    result = await service.settle(
        1, _Phrase(), _Topic(), c.CardState(typing=True), answer=_Phrase.en
    )
    assert result.passed
    assert service._repo.recorded["passed"] is True


@pytest.mark.asyncio
async def test_the_phrase_is_remembered_so_it_does_not_come_straight_back():
    service = _service()
    await service.settle(1, _Phrase(), _Topic(), c.CardState(typing=True), answer=_Phrase.en)
    assert service._repo.recorded["phrase_id"] == _Phrase.id


def test_the_score_is_hidden_until_it_means_something():
    """0.8 after three cards reads as a verdict on the learner rather than as
    a start."""
    service = _service()
    fresh = service._render(
        topic=_Topic(), phrase=_Phrase(), score=0.0, state=c.CardState()
    )
    started = service._render(
        topic=_Topic(), phrase=_Phrase(), score=0.4, state=c.CardState()
    )
    assert "·" not in fresh.text.splitlines()[0]
    assert "2.0" in started.text.splitlines()[0]
