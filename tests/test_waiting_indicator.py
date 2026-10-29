"""The learner can see that a slow check is running.

A typed answer that isn't an exact match is sent to the model, and their own
message is deleted on the way in. Without these signals the chat shows nothing
at all for the length of that call — up to the timeout, twice over with the
retry — which reads as a dropped answer, not as a pending one.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import waiting


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []
        self.edits: list[str] = []

    async def send_chat_action(self, chat_id, action):
        self.actions.append((chat_id, action))

    async def edit_message_text(self, text, chat_id=None, message_id=None, parse_mode=None):
        self.edits.append(text)


@pytest.mark.asyncio
async def test_a_wait_types_and_animates_the_card(monkeypatch):
    monkeypatch.setattr(waiting, "FRAME_EVERY", 0.01)
    monkeypatch.setattr(waiting, "ACTION_EVERY", 0.01)
    bot = FakeBot()
    async with waiting.checking(bot, 42, 7, head="✍️ <b>i goed</b>"):
        await asyncio.sleep(0.08)

    assert ("typing" in {a for _c, a in bot.actions}), "no «печатает…» while the model was asked"
    assert len(bot.actions) > 1, "the action expires after ~5s — it has to be re-sent"
    # The answer stays on screen, and the dots move.
    assert all("i goed" in e for e in bot.edits)
    assert len(set(bot.edits)) > 1, "a frozen line is what we are trying to fix"


@pytest.mark.asyncio
async def test_the_wait_stops_when_the_verdict_arrives(monkeypatch):
    monkeypatch.setattr(waiting, "FRAME_EVERY", 0.01)
    monkeypatch.setattr(waiting, "ACTION_EVERY", 0.01)
    bot = FakeBot()
    async with waiting.checking(bot, 42, 7):
        await asyncio.sleep(0.03)
    after = len(bot.edits)
    await asyncio.sleep(0.05)
    assert len(bot.edits) == after, "the animation outlived the answer and overwrote the verdict"


@pytest.mark.asyncio
async def test_a_broken_edit_never_costs_the_answer(monkeypatch):
    """Telegram refusing an edit is not a reason to lose the verdict."""
    monkeypatch.setattr(waiting, "FRAME_EVERY", 0.01)
    monkeypatch.setattr(waiting, "ACTION_EVERY", 0.01)

    class Broken(FakeBot):
        async def edit_message_text(self, *a, **kw):
            raise RuntimeError("message is not modified")

        async def send_chat_action(self, *a, **kw):
            raise RuntimeError("chat not found")

    async with waiting.checking(Broken(), 42, 7):
        await asyncio.sleep(0.03)


@pytest.mark.asyncio
async def test_without_a_card_only_the_action_runs(monkeypatch):
    monkeypatch.setattr(waiting, "FRAME_EVERY", 0.01)
    monkeypatch.setattr(waiting, "ACTION_EVERY", 0.01)
    bot = FakeBot()
    async with waiting.checking(bot, 42, None):
        await asyncio.sleep(0.03)
    assert bot.actions and not bot.edits
