"""Stale push cards used to linger in chat (day-rollover wiped inflight without
deleting the old message; a stale-answer tap only showed a toast). Now we drop
the ghost — or at least strip its buttons when Telegram refuses delete."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.push_service import PushService


class FakeBot:
    def __init__(self, delete_raises: bool = False) -> None:
        self.deleted: list[tuple[int, int]] = []
        self.markup_stripped: list[tuple[int, int]] = []
        self._delete_raises = delete_raises

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        if self._delete_raises:
            raise RuntimeError("message too old")
        self.deleted.append((chat_id, message_id))

    async def edit_message_reply_markup(
        self, *, chat_id: int, message_id: int, reply_markup: Any
    ) -> None:
        assert reply_markup is None
        self.markup_stripped.append((chat_id, message_id))


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


class FakeQueryMessage:
    def __init__(self, bot: FakeBot, chat_id: int = 555, message_id: int = 1001) -> None:
        self.bot = bot
        self.chat = SimpleNamespace(id=chat_id)
        self.message_id = message_id
        self.deleted = False
        self.markup_stripped = False

    async def delete(self) -> None:
        if self.bot._delete_raises:
            raise RuntimeError("message too old")
        self.deleted = True

    async def edit_reply_markup(self, reply_markup: Any) -> None:
        assert reply_markup is None
        self.markup_stripped = True


class FakeQuery:
    def __init__(self, message: FakeQueryMessage | None) -> None:
        self.message = message
        self.answered: list[Any] = []

    async def answer(self, text: Any = None, show_alert: bool = False) -> None:
        self.answered.append((text, show_alert))


@pytest.fixture()
def svc_with_bot() -> tuple[PushService, FakeBot, FakeRedis]:
    bot = FakeBot()
    redis = FakeRedis()
    svc = PushService(session=None, redis=redis, bot=bot)  # type: ignore[arg-type]
    return svc, bot, redis


async def test_delete_falls_back_to_stripping_markup(monkeypatch):
    """When Telegram refuses delete (>48h), at least the buttons go away so the
    user can't tap a ghost card."""
    bot = FakeBot(delete_raises=True)
    redis = FakeRedis()
    svc = PushService(session=None, redis=redis, bot=bot)  # type: ignore[arg-type]
    await svc._delete(123, 999)
    assert bot.deleted == []
    assert bot.markup_stripped == [(123, 999)]


async def test_delete_uses_delete_when_possible(svc_with_bot):
    svc, bot, _ = svc_with_bot
    await svc._delete(123, 999)
    assert bot.deleted == [(123, 999)]
    assert bot.markup_stripped == []


async def test_handle_answer_stale_deletes_ghost_card(svc_with_bot):
    """A tap on yesterday's card (inflight cleared by day-rollover) should
    delete the ghost message, not leave it sitting with live buttons."""
    svc, bot, redis = svc_with_bot
    user = SimpleNamespace(id=7, telegram_id=999)
    ut = SimpleNamespace(learning_pace="normal")
    # State has NO inflight — user is tapping yesterday's card.
    await redis.set(f"push:{user.id}", json.dumps({"day": "2026-05-28", "inflight": None}))
    msg = FakeQueryMessage(bot, chat_id=999, message_id=42)
    query = FakeQuery(msg)
    await svc.handle_answer(user, ut, uw_id=12345, idx=0, query=query)  # type: ignore[arg-type]
    assert msg.deleted is True
    assert query.answered  # toast still shown
    assert query.answered[0][0] == "⌛ Эта карточка уже неактуальна."


async def test_handle_answer_stale_card_too_old_strips_markup_instead(monkeypatch):
    bot = FakeBot(delete_raises=True)
    redis = FakeRedis()
    svc = PushService(session=None, redis=redis, bot=bot)  # type: ignore[arg-type]
    user = SimpleNamespace(id=7, telegram_id=999)
    ut = SimpleNamespace(learning_pace="normal")
    await redis.set(f"push:{user.id}", json.dumps({"day": "x", "inflight": None}))
    msg = FakeQueryMessage(bot, message_id=42)
    msg.bot._delete_raises = True
    query = FakeQuery(msg)
    await svc.handle_answer(user, ut, uw_id=12345, idx=0, query=query)  # type: ignore[arg-type]
    assert msg.deleted is False
    assert msg.markup_stripped is True


async def test_show_rule_on_stale_card_cleans_it_up(svc_with_bot):
    """Tapping 📖 Правило on a card that's no longer the inflight (day rolled
    over, etc.) should delete the ghost, not send a new rule message."""
    svc, bot, redis = svc_with_bot
    user = SimpleNamespace(id=7, telegram_id=999)
    # Inflight is for a DIFFERENT exercise — the tapped card is stale.
    await redis.set(
        f"push:{user.id}",
        json.dumps({"day": "x", "inflight": {"kind": "grammar", "id": 999}}),
    )
    msg = FakeQueryMessage(bot, message_id=42)
    query = FakeQuery(msg)
    await svc.show_rule(user, ugi_id=12345, query=query)  # type: ignore[arg-type]
    assert msg.deleted is True
