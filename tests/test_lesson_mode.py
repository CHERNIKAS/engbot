"""Lesson mode: the day's plan as one sitting instead of pushes.

What the owner asked for, 2026-10-02:
- a menu button starts it; cards follow each answer at once, pushes pause;
- «⏹ Закончить обучение» ends it: plan done → praise and wait for tomorrow,
  otherwise pushes finish the rest;
- 10 minutes of silence → «Ты тут?» with «Да»; «Да» carries on, and another
  10 silent minutes ask again; no answer within 5 minutes → back to pushes.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.bot.texts import LESSON_DAY_DONE, LESSON_PING
from app.services import day_plan_service as dps
from app.services import push_service as ps
from app.services.push_service import PushService


class _Redis:
    def __init__(self):
        self.kv: dict = {}
        self.sets: dict = {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(str(member))

    async def srem(self, key, member):
        self.sets.setdefault(key, set()).discard(str(member))

    async def smembers(self, key):
        return set(self.sets.get(key, set()))


class _Session:
    async def commit(self):
        pass

    async def rollback(self):
        pass


_USER = SimpleNamespace(id=1, telegram_id=99, timezone="UTC", level="A1", streak_days=0)


def _service(redis=None):
    svc = PushService.__new__(PushService)
    svc._redis = redis or _Redis()
    svc._session = _Session()
    svc._bot = object()
    svc._s = SimpleNamespace(push_gap_min_minutes=2, push_gap_max_minutes=15)
    svc.sent: list = []
    svc.deleted: list = []

    async def _raw_send(chat_id, text, kb=None, **kwargs):
        svc.sent.append((text, kb, kwargs.get("kind")))
        return 700 + len(svc.sent)

    async def _delete(chat_id, msg_id):
        svc.deleted.append(msg_id)

    async def _plan_left(user):
        return svc.left

    svc._raw_send = _raw_send
    svc._delete = _delete
    svc._plan_left = _plan_left
    svc.left = 5
    return svc


def _state(svc) -> dict:
    raw = svc._redis.kv.get(ps._KEY.format(user_id=_USER.id))
    return json.loads(raw) if raw else {}


async def _put(svc, state):
    await svc._save(_USER.id, state)
    if state.get("lesson"):
        await svc._redis.sadd(ps._LESSON_SET, _USER.id)


def _now():
    return datetime.now(timezone.utc).timestamp()


# ---- pushes stand aside ---------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_push_tick_sends_nothing_during_a_lesson():
    svc = _service()
    svc._window = lambda user, ut: (0, 24)
    await _put(svc, {"day": "x", "inflight": None, "lesson": {"since": _now(), "active_ts": _now()}})
    assert await svc.run_tick(_USER, None) is False
    assert svc.sent == []


# ---- the clock ------------------------------------------------------------- #


class _Users:
    def __init__(self, session):
        pass

    async def get(self, uid):
        return _USER


@pytest.mark.asyncio
async def test_ten_silent_minutes_ask_if_the_learner_is_there(monkeypatch):
    svc = _service()
    await _put(svc, {"inflight": {"kind": "word", "id": 1, "msg_id": 5},
                     "lesson": {"since": _now() - 700, "active_ts": _now() - ps.LESSON_IDLE_SECONDS - 5}})
    monkeypatch.setattr("app.infrastructure.repositories.users.UserRepository", _Users)
    await svc.run_lessons()

    assert [s[0] for s in svc.sent] == [LESSON_PING]
    lesson = _state(svc)["lesson"]
    assert lesson["ping_ts"] and lesson["ping_msg_id"]


@pytest.mark.asyncio
async def test_a_learner_who_answered_recently_is_left_alone(monkeypatch):
    svc = _service()
    await _put(svc, {"inflight": None, "lesson": {"since": _now() - 300, "active_ts": _now() - 120}})

    monkeypatch.setattr("app.infrastructure.repositories.users.UserRepository", _Users)
    await svc.run_lessons()
    assert svc.sent == []


@pytest.mark.asyncio
async def test_no_answer_to_the_question_hands_the_plan_back_to_pushes(monkeypatch):
    svc = _service()
    asked = _now() - ps.LESSON_PING_TIMEOUT_SECONDS - 5
    await _put(svc, {"inflight": {"kind": "word", "id": 1, "msg_id": 5, "retry_ts": 0},
                     "lesson": {"since": asked - 900, "active_ts": asked - 600,
                                "ping_ts": asked, "ping_msg_id": 42}})

    monkeypatch.setattr("app.infrastructure.repositories.users.UserRepository", _Users)
    await svc.run_lessons()

    state = _state(svc)
    assert "lesson" not in state
    assert 42 in svc.deleted  # the unanswered «Ты тут?» goes
    assert svc._redis.sets[ps._LESSON_SET] == set()
    # Pushes take over: not this instant, and the waiting card on the push clock.
    assert state["next_ts"] > _now()
    assert state["inflight"]["retry_ts"] > _now()
    text, kb, _kind = svc.sent[-1]
    assert "пуши" in text and kb is not None  # the menu comes back


@pytest.mark.asyncio
async def test_any_tap_counts_as_here_and_takes_the_question_back():
    svc = _service()
    await _put(svc, {"inflight": {"kind": "word", "id": 1, "msg_id": 5},
                     "lesson": {"since": _now() - 900, "active_ts": _now() - 650,
                                "ping_ts": _now() - 30, "ping_msg_id": 42}})
    await svc._lesson_after(_USER, None)
    lesson = _state(svc)["lesson"]
    assert "ping_ts" not in lesson and 42 in svc.deleted
    assert _now() - lesson["active_ts"] < 5


# ---- next card at once ----------------------------------------------------- #


class _Plan:
    def __init__(self, kinds, done=0):
        self.id = 9
        self.items = [{"kind": k, "done": i < done} for i, k in enumerate(kinds)]


class _PlanService:
    plan = None
    opened = False
    closed_today = False

    def __init__(self, session):
        pass

    async def ensure_plan(self, user, track, day):
        return type(self).plan, type(self).opened

    progress = staticmethod(dps.DayPlanService.progress)
    next_kind = staticmethod(dps.DayPlanService.next_kind)

    async def mark_done(self, plan, kind):
        for item in plan.items:
            if item["kind"] == kind and not item["done"]:
                item["done"] = True
                return

    async def open_plan_or_none(self, user_id, track):
        return type(self).plan

    async def close_if_complete(self, plan):
        type(self).plan = None  # closed; the day summary is not under test here
        return False


def _step_service(monkeypatch, served: list, fill=True):
    svc = _service()
    svc._window = lambda user, ut: (0, 24)
    svc._grammar = SimpleNamespace()

    async def pending_rule(uid, track):
        return None

    svc._grammar.pending_rule = pending_rule

    async def _serve(user, ut, kind, done, total, state, now_ts):
        served.append(kind)
        if fill:
            state["inflight"] = {"kind": "word", "id": 3, "msg_id": 800}
        return fill

    async def today_done(user, ut):
        return _PlanService.closed_today

    svc._serve = _serve
    svc.today_done = today_done

    class _UT:
        def __init__(self, session):
            pass

        async def get(self, uid, track):
            return SimpleNamespace(settings={})

    monkeypatch.setattr("app.infrastructure.repositories.user_tracks.UserTrackRepository", _UT)
    monkeypatch.setattr(ps, "DayPlanService", _PlanService)
    return svc


@pytest.mark.asyncio
async def test_a_settled_card_is_followed_by_the_next_one_at_once(monkeypatch):
    served: list = []
    svc = _step_service(monkeypatch, served)
    _PlanService.plan, _PlanService.opened = _Plan(["repeat", "new_word"], done=1), False
    await _put(svc, {"inflight": None, "lesson": {"since": _now(), "active_ts": _now()}})

    await svc._lesson_after(_USER, None)

    assert served == ["new_word"]
    assert _state(svc)["inflight"]["msg_id"] == 800


@pytest.mark.asyncio
async def test_a_finished_day_ends_the_lesson_with_praise(monkeypatch):
    served: list = []
    svc = _step_service(monkeypatch, served)
    _PlanService.plan, _PlanService.closed_today = None, True
    await _put(svc, {"inflight": None, "lesson": {"since": _now(), "active_ts": _now()}})

    await svc._lesson_after(_USER, None)

    assert served == []
    assert "lesson" not in _state(svc)
    assert svc.sent[-1][0] == LESSON_DAY_DONE
    _PlanService.closed_today = False


@pytest.mark.asyncio
async def test_an_unfillable_slot_is_skipped_not_waited_on(monkeypatch):
    served: list = []
    svc = _step_service(monkeypatch, served, fill=False)
    plan = _Plan(["phrase", "new_word"])
    _PlanService.plan, _PlanService.opened = plan, False
    state = {"inflight": None, "lesson": {"since": _now(), "active_ts": _now()}}
    await svc._lesson_step(_USER, state)
    # Each dead slot is ticked so the loop moves on and ends, instead of the
    # lesson stalling on a card that will never come.
    assert served[:2] == ["phrase", "new_word"]
    assert all(i["done"] for i in plan.items)


# ---- the button ------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_ending_with_cards_left_says_pushes_will_finish_them():
    svc = _service()
    svc.left = 4
    await _put(svc, {"inflight": None, "lesson": {"since": _now(), "active_ts": _now()}})
    await PushService.end_lesson.__wrapped__(svc, _USER)
    assert "lesson" not in _state(svc)
    assert "4" in svc.sent[-1][0]


@pytest.mark.asyncio
async def test_ending_with_the_plan_done_is_praise():
    svc = _service()
    svc.left = 0
    await _put(svc, {"inflight": None, "lesson": {"since": _now(), "active_ts": _now()}})
    await PushService.end_lesson.__wrapped__(svc, _USER)
    assert svc.sent[-1][0] == LESSON_DAY_DONE


# ---- one plan a day -------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_second_plan_on_the_day_the_first_one_closed():
    """Found while building this: the tick after a plan closed composed another
    one for the same day, so «жди завтра» was never true."""
    svc = dps.DayPlanService.__new__(dps.DayPlanService)

    class _Plans:
        async def open_plan(self, user_id, track):
            return None

        async def closed_on(self, user_id, track, day):
            return day == date(2026, 10, 3)

    svc._plans = _Plans()

    async def _boom(*a, **k):
        raise AssertionError("composed a plan on a finished day")

    svc._top_up = _boom
    assert await svc.ensure_plan(_USER, None, date(2026, 10, 3)) == (None, False)
