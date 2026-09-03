from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message

from app.bot.middlewares.placement_gate import PlacementGateMiddleware


def FakeMessage(text: str = "hi") -> Message:
    """MagicMock(spec=Message) satisfies the middleware's isinstance checks."""
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def FakeCallback(data: str) -> CallbackQuery:
    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.answer = AsyncMock()
    return cb


def _user(level=None, onboarded=True):
    return SimpleNamespace(id=1, level=level, onboarding_completed=onboarded)


async def _run(event, user):
    calls = []

    async def handler(e, d):
        calls.append(e)
        return "passed"

    result = await PlacementGateMiddleware()(handler, event, {"user": user})
    return result, calls


# ---- who the gate holds ----


async def test_onboarded_user_without_a_level_is_blocked():
    msg = FakeMessage()
    result, calls = await _run(msg, _user(level=None))
    assert calls == [] and result is None
    msg.answer.assert_awaited_once()
    assert msg.answer.await_args.kwargs["reply_markup"] is not None  # carries the button


async def test_user_with_a_level_passes_through():
    _result, calls = await _run(FakeMessage(), _user(level="B1"))
    assert len(calls) == 1


async def test_user_still_in_onboarding_passes_through():
    """Onboarding runs the test itself — blocking here would lock them out of
    the only flow that could free them."""
    _result, calls = await _run(FakeMessage(), _user(level=None, onboarded=False))
    assert len(calls) == 1


async def test_anonymous_update_passes_through():
    _result, calls = await _run(FakeMessage(), None)
    assert len(calls) == 1


# ---- what a blocked user may still press ----


async def test_blocked_user_may_start_the_test():
    _result, calls = await _run(FakeCallback("ob:lvl_gate::"), _user(level=None))
    assert len(calls) == 1


async def test_blocked_user_may_answer_test_cards():
    _result, calls = await _run(FakeCallback("ob:lvl:2:"), _user(level=None))
    assert len(calls) == 1


async def test_blocked_user_cannot_use_the_rest_of_the_bot():
    for data in ("mm:study:", "st:start:", "pk:open:", "set:open:", "ob:start::"):
        cb = FakeCallback(data)
        _result, calls = await _run(cb, _user(level=None))
        assert calls == [], data
        cb.answer.assert_awaited_once()


async def test_blocked_user_cannot_skip_the_test():
    """The skip path is gone from the UI; a hand-crafted callback must not
    resurrect it, or the gate hands out the very default it exists to avoid."""
    cb = FakeCallback("ob:lvl_skip::")
    _result, calls = await _run(cb, _user(level=None))
    assert calls == []


async def test_a_typed_message_from_a_blocked_user_is_answered_not_forwarded():
    msg = FakeMessage("/start")
    _result, calls = await _run(msg, _user(level=None))
    assert calls == []
    msg.answer.assert_awaited_once()
