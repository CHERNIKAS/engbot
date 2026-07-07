from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import CourseCB, NavCB
from app.bot.keyboards.common import home_button


def course_start_kb() -> InlineKeyboardMarkup:
    """Shown when the user isn't enrolled yet."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать курс", callback_data=CourseCB(action="start").pack())],
            [home_button()],
        ]
    )


def course_progress_kb(finished: bool) -> InlineKeyboardMarkup:
    """Shown when the user is enrolled — map + pause."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🗺 Карта курса", callback_data=CourseCB(action="map").pack())]
    ]
    if not finished:
        rows.append(
            [InlineKeyboardButton(text="⏸ Пауза", callback_data=CourseCB(action="pause").pack())]
        )
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_map_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data=CourseCB(action="open").pack())],
            [home_button()],
        ]
    )


def course_onboarding_offer_kb() -> InlineKeyboardMarkup:
    """Offer to start the course right after onboarding."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать курс", callback_data=CourseCB(action="start").pack())],
            [InlineKeyboardButton(text="📦 Соберу сам", callback_data=NavCB(action="home").pack())],
        ]
    )


def course_paused_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить курс", callback_data=CourseCB(action="start").pack())],
            [home_button()],
        ]
    )
