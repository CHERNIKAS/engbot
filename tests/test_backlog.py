from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.domain.enums import LearningTrack
from app.services.backlog_service import PARK_DAYS, BacklogService

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


class FakeUserWords:
    def __init__(self, active: int, candidates: int | None = None):
        self._active = active
        self._candidates = active if candidates is None else candidates
        self.parked: list[int] = []
        self.parked_until: datetime | None = None
        self.asked_for: int | None = None

    async def count_active(self, user_id, track):
        return self._active

    async def pick_backlog_to_park(self, user_id, track, limit, now=None):
        self.asked_for = limit
        rows = min(limit, self._candidates)
        return [(SimpleNamespace(id=100 + i), SimpleNamespace(writing=f"w{i}")) for i in range(rows)]

    async def park_words(self, user_id, user_word_ids, until):
        ids = list(user_word_ids)
        self.parked.extend(ids)
        self.parked_until = until
        return len(ids)


class FakeReviews:
    def __init__(self, rate):
        self._rate = rate

    async def typical_daily_answers(self, user_id, track, days=60):
        return self._rate


def _service(active, rate, candidates=None):
    svc = BacklogService.__new__(BacklogService)
    svc._session = None
    svc._uw = FakeUserWords(active, candidates)
    svc._reviews = FakeReviews(rate)
    return svc


# ---- what it proposes ----


async def test_the_prod_case_is_offered():
    """User 1: 63 active words on ~12 answers a day, receiving nothing new."""
    offer = await _service(active=63, rate=12.0).offer(1, LearningTrack.ENGLISH)
    assert offer.worth_offering
    assert offer.count > 0
    assert offer.active == 63


async def test_a_healthy_pool_is_left_alone():
    offer = await _service(active=10, rate=12.0).offer(1, LearningTrack.ENGLISH)
    assert not offer.worth_offering
    assert offer.count == 0


async def test_one_offer_never_takes_more_than_half():
    """Handing over three quarters of someone's active words in a single tap
    reads as loss, even when every one of them returns."""
    offer = await _service(active=63, rate=12.0).offer(1, LearningTrack.ENGLISH)
    assert offer.count <= offer.active // 2


# ---- what it does ----


async def test_it_parks_and_reports_what_is_left():
    svc = _service(active=63, rate=12.0)
    parked, left = await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert parked > 0
    assert left == 63 - parked
    assert len(svc._uw.parked) == parked


async def test_parked_words_come_back_on_their_own():
    """Snoozed, not archived — the user gets them back without doing anything."""
    svc = _service(active=63, rate=12.0)
    await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert svc._uw.parked_until is not None
    assert (svc._uw.parked_until - NOW).days == PARK_DAYS


async def test_a_healthy_pool_is_never_touched():
    svc = _service(active=10, rate=12.0)
    parked, left = await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert parked == 0
    assert left == 10
    assert svc._uw.parked == []


async def test_the_count_is_recomputed_not_taken_from_the_button():
    """The offer may have sat on screen while the user answered cards; acting
    on a stale number would take more than it should."""
    svc = _service(active=63, rate=12.0)
    offer = await svc.offer(1, LearningTrack.ENGLISH)
    svc._uw._active = 20  # they worked through some in the meantime
    parked, _left = await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert parked < offer.count


async def test_it_parks_no_more_than_the_pool_can_give():
    svc = _service(active=63, rate=12.0, candidates=4)
    parked, _left = await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert parked == 4


# ---- holes found by mutation testing ----


async def test_parked_words_stay_away_long_enough_to_matter():
    """The check above compares against PARK_DAYS itself, so PARK_DAYS = 0 —
    parking that parks nothing — passed it. The pool only drains if the words
    are gone for weeks, not hours."""
    svc = _service(active=63, rate=12.0)
    await svc.park(1, LearningTrack.ENGLISH, now=NOW)
    assert (svc._uw.parked_until - NOW).days >= 14


def test_a_single_word_is_still_worth_offering():
    from app.services.backlog_service import BacklogOffer

    assert BacklogOffer(active=10, target=8, count=1).worth_offering
    assert not BacklogOffer(active=10, target=8, count=0).worth_offering
