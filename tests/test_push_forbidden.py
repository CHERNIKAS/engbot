"""When a push send hits TelegramForbiddenError (user blocked the bot),
_raw_send must RE-RAISE it so run_all can disable push for that user. Any other
send error stays swallowed (transient — keep trying)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.services.push_service import PushService


class _ForbiddenBot:
    async def send_message(self, *a, **k):
        raise TelegramForbiddenError(method=SimpleNamespace(), message="bot was blocked by the user")


class _FlakyBot:
    async def send_message(self, *a, **k):
        raise RuntimeError("transient network error")


def _svc(bot) -> PushService:
    return PushService(session=None, redis=None, bot=bot)  # type: ignore[arg-type]


async def test_raw_send_reraises_forbidden():
    with pytest.raises(TelegramForbiddenError):
        await _svc(_ForbiddenBot())._raw_send(123, "hi", None)


async def test_raw_send_swallows_other_errors():
    assert await _svc(_FlakyBot())._raw_send(123, "hi", None) is None


async def test_raw_send_no_bot_returns_none():
    assert await _svc(None)._raw_send(123, "hi", None) is None
