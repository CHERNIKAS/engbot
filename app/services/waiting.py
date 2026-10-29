"""Something visible while the checker thinks.

A typed answer that isn't an exact match goes to the model, and that round trip
costs up to `answer_check_timeout_seconds` — twice, with the retry. Until now
the chat said nothing about it: the learner's own message is deleted (the card
carries the verdict, so leaving the attempt behind turns the chat into a log of
half-remembered sentences), and on the constructor path it is deleted *before*
the call. So the answer vanished and the card sat there unchanged for up to
sixteen seconds — indistinguishable from the bot having dropped it.

Two signals, because one alone is not enough. The chat action is Telegram's own
«печатает…» at the top of the window, which is what a human chat looks like
while someone replies — but it is invisible if the card is scrolled up, and it
expires after five seconds, so it has to be re-sent. The card edit puts the
waiting where the learner is looking, and animating the dots is what separates
«it's working» from «it's frozen».

Nothing here is allowed to break an answer: every call is best-effort, and the
checker's result is never held up by a failed edit.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.logging_setup import get_logger

log = get_logger("waiting")

# Telegram clears a chat action after ~5s; re-sent a little sooner so the
# indicator never blinks out mid-check.
ACTION_EVERY = 4.0
# One edit per frame, so the cadence is also the edit rate. Telegram tolerates
# about a message a second per chat; this leaves room to spare.
FRAME_EVERY = 1.6
# Dots rather than a spinner: a spinner glyph renders at a different width in
# every Telegram client and makes the line jump.
FRAMES = ("⏳ Проверяю ответ", "⏳ Проверяю ответ .", "⏳ Проверяю ответ . .", "⏳ Проверяю ответ . . .")


async def _animate(bot, chat_id: int, msg_id: int, head: str) -> None:
    """Edit the card through the frames until cancelled."""
    i = 0
    while True:
        text = f"{head}\n\n<i>{FRAMES[i % len(FRAMES)]}</i>" if head else FRAMES[i % len(FRAMES)]
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML"
            )
        except Exception:  # noqa: BLE001 — a lost frame is not worth a failed answer
            pass
        i += 1
        await asyncio.sleep(FRAME_EVERY)


async def _keep_typing(bot, chat_id: int) -> None:
    """Hold Telegram's «печатает…» up for as long as we're thinking."""
    while True:
        try:
            await bot.send_chat_action(chat_id, "typing")
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(ACTION_EVERY)


@asynccontextmanager
async def checking(bot, chat_id: int, msg_id: int | None = None, head: str = "") -> AsyncIterator[None]:
    """Show that the answer is being checked, for the length of the block.

    `msg_id` is the card in flight: it is animated in place and then overwritten
    by the verdict the caller writes, so the waiting leaves nothing behind.
    Without it only the chat action runs — right for a path that has no message
    of its own to animate.

    `head` is kept above the waiting line, so a card that still shows the
    sentence keeps showing it while the model is consulted.
    """
    tasks = [asyncio.create_task(_keep_typing(bot, chat_id))]
    if msg_id:
        tasks.append(asyncio.create_task(_animate(bot, chat_id, int(msg_id), head)))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
