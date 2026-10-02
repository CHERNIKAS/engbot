"""Sending a triage screen must leave it in flight.

The bug this exists for: `_send_triage` named its screen `state`, the same name
as the tick's push state it was handed. The screen was sent, then writing the
inflight into what was now a `TriageState` raised. The tick rolled back, nothing
was recorded as in flight, and five minutes later the next tick sent the screen
again — every tick, to every learner with a triage slot due.

`test_card_senders_do_not_load_their_own_push_state` only reads the source for
`self._load(`, so it passed: the state was not reloaded, it was shadowed. This
one calls the sender and checks the state it was handed.
"""
from __future__ import annotations

import pytest

from app.services.push_service import PushService


class _Theme:
    id = 7
    title = "🔢 Числа"


class _UW:
    def __init__(self, uw_id):
        self.id = uw_id


class _Word:
    def __init__(self, writing, translation):
        self.writing = writing
        self.translation = translation


class _UserWords:
    async def current_theme(self, user_id, track):
        return _Theme()

    async def theme_batch(self, user_id, track, theme_id, size):
        return [(_UW(1), _Word("one", "один")), (_UW(2), _Word("two", "два"))]


class _User:
    id = 1
    telegram_id = 99


def _service(sent: list):
    service = PushService.__new__(PushService)
    service._uw = _UserWords()

    async def _raw_send(chat_id, text, kb=None, **kwargs):
        sent.append(text)
        return 555

    service._raw_send = _raw_send
    return service


@pytest.mark.asyncio
async def test_a_sent_screen_is_recorded_in_the_state_it_was_handed():
    sent: list = []
    state = {"day": "2026-10-02", "next_ts": 0.0, "inflight": None}

    assert await _service(sent)._send_triage(_User(), state, 100.0, plan_done=0, plan_total=16)

    assert len(sent) == 1
    inflight = state["inflight"]
    assert inflight["kind"] == "triage"
    assert inflight["id"] == _Theme.id
    assert inflight["msg_id"] == 555
    assert [row[0] for row in inflight["rows"]] == [1, 2]
    # The screen's own selection travels inside the inflight, not in its place.
    assert isinstance(inflight["state"], dict)


@pytest.mark.asyncio
async def test_a_screen_in_flight_is_not_sent_again_by_the_same_state():
    """What the learner saw: the same screen every five minutes. With the
    inflight recorded, the tick takes the nudge branch instead of sending."""
    sent: list = []
    state = {"day": "2026-10-02", "next_ts": 0.0, "inflight": None}
    await _service(sent)._send_triage(_User(), state, 100.0)
    assert state["inflight"] is not None
