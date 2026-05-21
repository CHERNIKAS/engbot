from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import SettingsCB
from app.bot.keyboards.common import cancel_button, home_button
from app.bot.texts import PACE_LABELS


def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎯 Дневная цель", callback_data=SettingsCB(action="goal").pack())],
        [InlineKeyboardButton(text="⚡ Темп обучения", callback_data=SettingsCB(action="pace").pack())],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def goal_values_kb(version: str = "") -> InlineKeyboardMarkup:
    values = [5, 10, 20, 50]
    row = [
        InlineKeyboardButton(
            text=str(v),
            callback_data=SettingsCB(action="goal_value", value=str(v), v=version).pack(),
        )
        for v in values
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [
                InlineKeyboardButton(
                    text="✍️ Своё",
                    callback_data=SettingsCB(action="goal_value", value="custom", v=version).pack(),
                )
            ],
            [cancel_button(), home_button()],
        ]
    )


def pace_kb(current: str, version: str = "") -> InlineKeyboardMarkup:
    rows = []
    for code, label in PACE_LABELS.items():
        text = f"{'✅ ' if code == current else ''}{label}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=SettingsCB(action="pace_value", value=code, v=version).pack(),
                )
            ]
        )
    rows.append([cancel_button(), home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
