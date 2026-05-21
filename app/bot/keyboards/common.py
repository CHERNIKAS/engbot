from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks.schema import NavCB


def home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🏠 В меню", callback_data=NavCB(action="home").pack())


def cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="❌ Отмена", callback_data=NavCB(action="cancel").pack())


def back_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="↩️ Назад", callback_data=NavCB(action="back").pack())


def navigation_row(*, with_back: bool = False, with_cancel: bool = False) -> list[InlineKeyboardButton]:
    row = []
    if with_back:
        row.append(back_button())
    if with_cancel:
        row.append(cancel_button())
    row.append(home_button())
    return row


def single_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[home_button()]])


def cancel_only_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[cancel_button(), home_button()]])
