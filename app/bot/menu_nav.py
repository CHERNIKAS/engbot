from __future__ import annotations

# Single-active-card navigation: the bot keeps just one "menu card" alive per
# user. Opening a new section deletes the previous card and the tap that opened
# it, and "🏠 В меню" deletes the card outright — so the chat doesn't fill up
# with stale "Главное меню" / menu echoes. The persistent bottom reply-keyboard
# survives message deletions, so navigation always stays available.

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message
from redis.asyncio import Redis

from app.config import get_settings

_CARD_KEY = "menucard:{user_id}"


def _key(user_id: int) -> str:
    return _CARD_KEY.format(user_id=user_id)


async def _safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:  # noqa: BLE001 — already gone / too old / no rights
        pass


async def send_menu_card(
    message: Message,
    redis: Redis,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> Message:
    """Replace the user's current menu card with a fresh one.

    Deletes the previously tracked card and the triggering tap message, sends the
    new card, and remembers it as the active one.
    """
    bot = message.bot
    chat_id = message.chat.id
    prev = await redis.get(_key(user_id))
    if prev:
        await redis.delete(_key(user_id))
        try:
            await _safe_delete(bot, chat_id, int(prev))
        except (TypeError, ValueError):
            pass
    # The tap that opened this menu (a bottom reply-button press) is noise.
    await _safe_delete(bot, chat_id, message.message_id)
    sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await redis.set(_key(user_id), str(sent.message_id), ex=get_settings().interaction_ttl_seconds)
    return sent


async def clear_menu_card(bot: Bot, redis: Redis, user_id: int, chat_id: int, message_id: int | None = None) -> None:
    """Drop the active menu card (used by '🏠 В меню' / cancel)."""
    tracked = await redis.get(_key(user_id))
    await redis.delete(_key(user_id))
    if message_id is not None:
        await _safe_delete(bot, chat_id, message_id)
    if tracked:
        try:
            tracked_id = int(tracked)
        except (TypeError, ValueError):
            return
        if tracked_id != message_id:
            await _safe_delete(bot, chat_id, tracked_id)
