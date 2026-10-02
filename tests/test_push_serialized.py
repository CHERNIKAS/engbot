"""Taps and the worker tick take turns on a learner's push state.

On 2026-10-02 a nudge fired while the learner was filling a constructor card:
the tick read the state, the learner tapped, the tick saved its older copy and
replaced the message. Taps on the old message were refused as stale ("the
button didn't answer"), the ones that raced each other were all applied, and the
sentence was graded wrong. Two things stop that: a per-learner lock around every
entry point, and no nudge for a card touched in the last few minutes.
"""
from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import push_service as ps
from app.services.push_service import PushService


def test_every_public_entry_point_takes_the_learners_lock():
    """An entry point added later without the lock reopens the race."""
    unlocked = []
    for name, fn in inspect.getmembers(PushService, inspect.iscoroutinefunction):
        if (name.startswith("handle_") or name == "show_rule") and not hasattr(fn, "__wrapped__"):
            unlocked.append(name)
    assert unlocked == []


def test_the_worker_ticks_each_learner_under_the_same_lock():
    src = inspect.getsource(PushService.run_all)
    assert "_user_lock(uid)" in src


@pytest.mark.asyncio
async def test_two_taps_on_one_learner_run_one_after_the_other():
    trace: list[str] = []

    class Svc:
        async def _lesson_after(self, user, bot):
            pass

        @ps._serialized
        async def tap(self, user, name):
            trace.append(f"{name}:in")
            await asyncio.sleep(0.01)  # the load → change → save window
            trace.append(f"{name}:out")

    user = SimpleNamespace(id=4242)
    await asyncio.gather(Svc().tap(user, "a"), Svc().tap(user, "b"))
    assert trace in (["a:in", "a:out", "b:in", "b:out"], ["b:in", "b:out", "a:in", "a:out"])


@pytest.mark.asyncio
async def test_different_learners_do_not_wait_for_each_other():
    trace: list[str] = []

    class Svc:
        async def _lesson_after(self, user, bot):
            pass

        @ps._serialized
        async def tap(self, user):
            trace.append(f"{user.id}:in")
            await asyncio.sleep(0.01)
            trace.append(f"{user.id}:out")

    await asyncio.gather(Svc().tap(SimpleNamespace(id=1)), Svc().tap(SimpleNamespace(id=2)))
    assert trace[:2] == ["1:in", "2:in"]


def _tick_service(state: dict, nudged: list):
    svc = PushService.__new__(PushService)
    svc._window = lambda user, ut: (0, 24)

    async def _load(uid):
        return state

    async def _save(uid, st):
        state.update(st)

    async def _renudge(user, inflight, attempts, now_ts):
        nudged.append(attempts)
        return 999

    async def _delete(chat_id, msg_id):
        pass

    svc._load = _load
    svc._save = _save
    svc._renudge = _renudge
    svc._delete = _delete
    svc._log_idle = lambda *a, **k: None
    return svc


def _state_with_card(touched_ago: float | None) -> dict:
    now = datetime.now(timezone.utc)
    inflight = {"kind": "phrase", "id": 6, "topic_id": 1, "msg_id": 100, "attempts": 1, "retry_ts": 0}
    if touched_ago is not None:
        inflight["touched_ts"] = now.timestamp() - touched_ago
    day = ps._push_day(now.astimezone(ps._tz("UTC")), 0)
    return {"day": day, "next_ts": 0.0, "inflight": inflight}


_USER = SimpleNamespace(id=1, telegram_id=99, timezone="UTC")


@pytest.mark.asyncio
async def test_a_card_being_worked_on_is_not_nudged():
    nudged: list = []
    state = _state_with_card(touched_ago=20)
    assert await _tick_service(state, nudged).run_tick(_USER, None) is False
    assert nudged == []
    assert state["inflight"]["msg_id"] == 100


@pytest.mark.asyncio
async def test_a_card_left_alone_is_still_nudged():
    """The grace must not switch nudging off: untouched, or touched long ago,
    the card comes back as before."""
    for touched_ago in (None, ps.TOUCH_GRACE_SECONDS + 60):
        nudged: list = []
        state = _state_with_card(touched_ago)
        assert await _tick_service(state, nudged).run_tick(_USER, None) is True
        assert nudged == [2]
        assert state["inflight"]["msg_id"] == 999
