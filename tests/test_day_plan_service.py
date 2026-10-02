"""Serving a plan: what gets ticked, what closes, and what must not stick.

The plan is the thing that makes a day finishable, so the failure that matters
is not "wrong card" — it is a plan that can never be closed, because an unclosed
plan is never replaced and blocks every day after it.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain import day_plan as rules
from app.domain.enums import LearningTrack
from app.services.day_plan_service import DayPlanService


class _FakePlan:
    def __init__(self, items, closed_at=None, size=28, opened_on=None):
        self.id = 1
        self.items = items
        self.closed_at = closed_at
        self.size = size
        self.opened_on = opened_on or date(2026, 9, 22)


class _FakeRepo:
    def __init__(self):
        self.saved = None
        self.closed = []

    async def save_items(self, plan_id, items):
        self.saved = items

    async def close(self, plan_id, now=None):
        self.closed.append(plan_id)


def _service():
    service = DayPlanService.__new__(DayPlanService)
    service._plans = _FakeRepo()
    return service


def _items(*kinds):
    return [{"kind": k, "done": False} for k in kinds]


def test_the_most_perishable_cards_are_served_first():
    """An interrupted session should still have done the part with a deadline:
    a word overdue for review is being forgotten right now, a new word is not."""
    composition = rules.compose(28, due_repeats=50, grammar_available=4, phrases_available=5, new_available=50)
    kinds = [i["kind"] for i in DayPlanService._items_for(composition)]
    assert kinds[0] == rules.REPEAT
    assert kinds.index(rules.GRAMMAR) < kinds.index(rules.NEW_WORD)
    assert len(kinds) == composition.total


@pytest.mark.asyncio
async def test_answering_ticks_exactly_one_slot_of_that_kind():
    service = _service()
    plan = _FakePlan(_items(rules.REPEAT, rules.REPEAT, rules.GRAMMAR))
    progress = await service.mark_done(plan, rules.REPEAT)
    assert progress.done == 1
    assert [i["done"] for i in plan.items] == [True, False, False]


@pytest.mark.asyncio
async def test_a_wrong_answer_still_ticks_the_slot():
    """The plan measures attendance, not accuracy — spaced repetition already
    handles being wrong, and requiring a correct answer would let one hard word
    hold the day open indefinitely."""
    service = _service()
    plan = _FakePlan(_items(rules.GRAMMAR))
    progress = await service.mark_done(plan, rules.GRAMMAR)
    assert progress.closed


@pytest.mark.asyncio
async def test_an_unfillable_slot_can_be_ticked_off():
    """The escape valve. If a theme has nothing left to teach, that slot must
    be closable without a card ever being sent, or the plan sticks forever."""
    service = _service()
    plan = _FakePlan(_items(rules.NEW_THEME_WORD, rules.REPEAT))
    await service.mark_done(plan, rules.NEW_THEME_WORD)
    assert service.next_kind(plan) == rules.REPEAT


@pytest.mark.asyncio
async def test_items_are_rewritten_wholesale_when_saved():
    """SQLAlchemy does not track mutations inside a JSONB column, so patching
    the list in place would flush nothing and lose the tick."""
    service = _service()
    plan = _FakePlan(_items(rules.REPEAT))
    await service.mark_done(plan, rules.REPEAT)
    assert service._plans.saved == [{"kind": rules.REPEAT, "done": True}]


def test_next_kind_is_none_once_everything_is_answered():
    plan = _FakePlan([{"kind": rules.REPEAT, "done": True}])
    assert DayPlanService.next_kind(plan) is None


@pytest.mark.asyncio
async def test_a_plan_closes_once_and_only_once():
    """The caller sends the day's summary on a True, so a second True would
    send it twice."""
    service = _service()
    plan = _FakePlan([{"kind": rules.REPEAT, "done": True}])
    assert await service.close_if_complete(plan) is True
    plan.closed_at = datetime.now(timezone.utc)
    assert await service.close_if_complete(plan) is False


@pytest.mark.asyncio
async def test_an_unfinished_plan_does_not_close():
    service = _service()
    plan = _FakePlan(_items(rules.REPEAT, rules.GRAMMAR))
    await service.mark_done(plan, rules.REPEAT)
    assert await service.close_if_complete(plan) is False
    assert service._plans.closed == []


def test_counts_by_kind_describes_the_plan_card():
    plan = _FakePlan(_items(rules.REPEAT, rules.REPEAT, rules.GRAMMAR, rules.PHRASE))
    assert DayPlanService.counts_by_kind(plan) == {
        rules.REPEAT: 2,
        rules.GRAMMAR: 1,
        rules.PHRASE: 1,
    }


class _FakeUser:
    id = 1
    level = "A1"


class _FakeWords:
    """Vocabulary counts, fixed — this group of tests is about grammar slots."""

    async def count_overdue(self, user_id, track):
        return 5

    async def count_new_startable(self, user_id, track, phrases=False):
        return 5

    async def current_theme(self, user_id, track):
        return None  # no theme — these tests are about grammar slots


class _FakeConstructor:
    def __init__(self, topic):
        self.topic = topic
        self.asked = False

    async def active_topic(self, user_id):
        self.asked = True
        return self.topic

    async def due_test_topic(self, user_id):
        return None


def _composing_service(topic):
    service = DayPlanService.__new__(DayPlanService)
    service._plans = _FakeRepo()
    service._words = _FakeWords()
    service._constructor = _FakeConstructor(topic)
    return service


@pytest.mark.asyncio
async def test_grammar_slots_are_booked_from_the_repository_that_serves_them():
    """The plan must ask whoever will actually produce the card.

    Booking slots off a second, different notion of "active topic" — one based
    on the old exercise rows rather than on constructor phrases — lets the plan
    promise four grammar cards that `open_card` then refuses to build. The
    slots tick off empty, and grammar vanishes from the day with nothing in the
    log to say so.
    """
    service = _composing_service(object())
    composition = await service._compose(_FakeUser(), LearningTrack.ENGLISH, 28)
    assert service._constructor.asked is True
    assert composition.grammar == rules.GRAMMAR_PER_DAY


@pytest.mark.asyncio
async def test_no_serveable_topic_means_no_grammar_slots():
    service = _composing_service(None)
    composition = await service._compose(_FakeUser(), LearningTrack.ENGLISH, 28)
    assert composition.grammar == 0


class _EmptyVocabWords:
    """A learner who owns nothing yet — the state a new user is in the moment
    onboarding ends."""

    def __init__(self):
        self.topped_up = False
        self.stocked = 0

    async def count_overdue(self, user_id, track):
        return 0

    async def current_theme(self, user_id, track):
        return None  # owns nothing, so there is no theme to triage

    async def count_new_startable(self, user_id, track, phrases=False):
        return self.stocked

    async def band_coverage(self, user_id, track):
        return 0, 0, 1044, 495


@pytest.mark.asyncio
async def test_a_brand_new_learner_gets_a_plan_not_an_empty_day():
    """Onboarding no longer ends in a placement test, so the first plan is the
    first thing that happens. If `_top_up` did not run before composing, a new
    user would get `(None, False)` — no plan, no cards, and nothing on screen
    saying why.
    """
    service = DayPlanService.__new__(DayPlanService)
    service._plans = _FakeRepo()
    words = _EmptyVocabWords()
    service._words = words
    service._constructor = _FakeConstructor(object())

    async def _top_up(user, track):
        words.stocked = 40  # what the catalogue top-up would put there

    service._top_up = _top_up
    service.refresh_level = lambda user, track: _noop()

    # Grammar alone would still make a plan — it comes from the topic list, not
    # from the learner's vocabulary — so an empty day would be four grammar
    # cards and no words at all.
    composition = await service._compose(_FakeUser(), LearningTrack.ENGLISH, 28)
    assert composition.total == rules.GRAMMAR_PER_DAY
    assert composition.new_frequency + composition.new_theme == 0

    await _top_up(None, None)
    composition = await service._compose(_FakeUser(), LearningTrack.ENGLISH, 28)
    assert composition.total > 0
    assert composition.new_frequency + composition.new_theme > 0, "новых слов нет"
    assert composition.grammar == rules.GRAMMAR_PER_DAY


async def _noop():
    return "A1"
