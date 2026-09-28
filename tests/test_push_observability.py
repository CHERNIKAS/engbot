"""What the push worker must say about itself.

Written after a user reported the same constructor card arriving twice, five
minutes apart, without a nudge marker. The report could be neither reproduced
nor ruled out: the bot logged nothing about sending cards at all, and the last
line in the log predated the cards by a day. Live Redis state looked healthy,
which proves nothing about what happened hours earlier.

So these tests pin the two things that made the report unanswerable — a send
leaves no trace, and silence is indistinguishable from breakage — plus the
alarm that would have caught July's spam bug before a human did.
"""
from __future__ import annotations

import pytest

from app.services.push_service import PushService


class _FakeRedis:
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    async def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key, seconds):
        self.expires[key] = seconds


def _service(redis=None):
    service = PushService.__new__(PushService)
    service._redis = redis
    service._bot = None
    return service


@pytest.mark.asyncio
async def test_the_rate_counter_never_touches_the_push_state_key():
    """The July bug was one writer clobbering `push:{uid}` with a stale
    snapshot. A counter that opened that key would join the same class of
    problem, so it gets a key of its own."""
    redis = _FakeRedis()
    await _service(redis)._note_send_rate(7)
    assert list(redis.counters) == ["pushrate:7"]
    assert not any(k.startswith("push:") for k in redis.counters)


@pytest.mark.asyncio
async def test_the_window_is_set_once_not_refreshed_on_every_send():
    """Re-setting the TTL on each send would slide the window forward forever
    and the counter would never reset, so the warning could not fire twice."""
    redis = _FakeRedis()
    service = _service(redis)
    for _ in range(5):
        await service._note_send_rate(7)
    assert redis.expires == {"pushrate:7": PushService.SEND_RATE_WINDOW_SECONDS}


@pytest.mark.asyncio
async def test_the_alarm_sits_below_what_the_july_bug_produced():
    """That bug sent ~40 cards in 3.5 hours — about 11 an hour — and a human
    noticed three hours in. The ceiling by design is 12 (one card per tick,
    twelve ticks an hour), and an ordinary day is two or three. The threshold
    has to sit between ordinary and broken."""
    assert 3 < PushService.SEND_RATE_WARN < 11


@pytest.mark.asyncio
async def test_telemetry_failure_never_stops_a_card():
    """A card the learner is waiting for must not be lost because a counter
    could not be written."""

    class _Broken:
        async def incr(self, key):
            raise RuntimeError("redis down")

    await _service(_Broken())._note_send_rate(1)  # must not raise


@pytest.mark.asyncio
async def test_a_service_without_redis_still_sends():
    await _service(None)._note_send_rate(1)  # must not raise
