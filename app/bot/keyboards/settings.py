from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import SettingsCB
from app.bot.keyboards.common import cancel_button, home_button
from app.bot.texts import PACE_LABELS


def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎯 Дневная цель", callback_data=SettingsCB(action="goal").pack())],
        [InlineKeyboardButton(text="⚡ Темп обучения", callback_data=SettingsCB(action="pace").pack())],
        [InlineKeyboardButton(text="🔔 Пуш-обучение", callback_data=SettingsCB(action="push_open").pack())],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_settings_kb(enabled: bool, ws: int, we: int) -> InlineKeyboardMarkup:
    toggle = "🔔 Пуши: ВКЛ ✅" if enabled else "🔕 Пуши: выкл"
    rows = [
        [InlineKeyboardButton(text=toggle, callback_data=SettingsCB(action="push_toggle").pack())],
        [
            InlineKeyboardButton(
                text=f"🕐 Окно: {ws:02d}:00–{we:02d}:00",
                callback_data=SettingsCB(action="push_win").pack(),
            )
        ],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_window_kb(ws: int, we: int) -> InlineKeyboardMarkup:
    starts = [6, 7, 8, 9, 10, 11, 12]
    ends = [18, 19, 20, 21, 22, 23, 24]
    row_s = [
        InlineKeyboardButton(
            text=(f"·{h}·" if h == ws else str(h)),
            callback_data=SettingsCB(action="push_win_set", value=f"s{h}").pack(),
        )
        for h in starts
    ]
    row_e = [
        InlineKeyboardButton(
            text=(f"·{h}·" if h == we else str(h)),
            callback_data=SettingsCB(action="push_win_set", value=f"e{h}").pack(),
        )
        for h in ends
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row_s,
            row_e,
            [InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="push_open").pack())],
        ]
    )


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
