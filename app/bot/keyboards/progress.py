from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import ProgressCB, PushCB


def progress_kb(has_managed: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_managed:
        rows.append(
            [InlineKeyboardButton(text="🗂 Архив и отложенные", callback_data=ProgressCB(action="managed").pack())]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def managed_words_kb(
    archived: list[tuple[int, str]], snoozed: list[tuple[int, str]]
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for uw_id, writing in archived:
        rows.append(
            [InlineKeyboardButton(text=f"↩️ {writing}", callback_data=PushCB(action="unarchive", uw_id=uw_id).pack())]
        )
    for uw_id, writing in snoozed:
        rows.append(
            [InlineKeyboardButton(text=f"⏰ {writing}", callback_data=PushCB(action="unsnooze", uw_id=uw_id).pack())]
        )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data=ProgressCB(action="open").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
