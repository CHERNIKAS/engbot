from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import SettingsCB
from app.bot.keyboards.common import home_button
from app.bot.texts import PACE_LABELS
from app.domain.pacing import PACE_OPTIONS, label_for


def _back_to_settings_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="open").pack())


def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎯 Дневная цель", callback_data=SettingsCB(action="goal").pack())],
        [InlineKeyboardButton(text="⚡ Темп обучения", callback_data=SettingsCB(action="pace").pack())],
        [InlineKeyboardButton(text="🔔 Пуш-обучение", callback_data=SettingsCB(action="push_open").pack())],
        [InlineKeyboardButton(text="🕐 Часовой пояс", callback_data=SettingsCB(action="tz_open").pack())],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# IANA timezone → label (CIS/Europe focus; DST handled by zoneinfo).
TZ_ZONES: list[tuple[str, str]] = [
    ("UTC", "🌍 UTC"),
    ("Europe/Kaliningrad", "Калининград +2"),
    ("Europe/Moscow", "Москва +3"),
    ("Europe/Samara", "Самара +4"),
    ("Asia/Yekaterinburg", "Екатеринбург +5"),
    ("Asia/Omsk", "Омск +6"),
    ("Asia/Krasnoyarsk", "Красноярск +7"),
    ("Asia/Irkutsk", "Иркутск +8"),
    ("Asia/Yakutsk", "Якутск +9"),
    ("Asia/Vladivostok", "Владивосток +10"),
    ("Asia/Magadan", "Магадан +11"),
    ("Asia/Kamchatka", "Камчатка +12"),
    ("Europe/Kyiv", "Киев +2/3"),
    ("Europe/Minsk", "Минск +3"),
    ("Asia/Almaty", "Алматы +5"),
    ("Asia/Tbilisi", "Тбилиси +4"),
    ("Asia/Yerevan", "Ереван +4"),
    ("Asia/Tashkent", "Ташкент +5"),
    ("Europe/Berlin", "Берлин +1/2"),
    ("Europe/London", "Лондон 0/+1"),
]


def timezone_kb(current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for zone, label in TZ_ZONES:
        mark = "✅ " if zone == current else ""
        row.append(
            InlineKeyboardButton(
                text=f"{mark}{label}",
                callback_data=SettingsCB(action="tz_set", value=zone).pack(),
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="open").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_settings_kb(ws: int, we: int, pace: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🕐 Окно: {ws:02d}:00–{we:02d}:00",
                    callback_data=SettingsCB(action="push_win").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🚀 Новые слова: {label_for(pace)}",
                    callback_data=SettingsCB(action="newpace").pack(),
                )
            ],
            [_back_to_settings_button(), home_button()],
        ]
    )


def new_pace_kb(current: int) -> InlineKeyboardMarkup:
    """Pick how many NEW words/day the push introduces (3 / 7 / 15 / 25)."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if value == current else ''}{emoji} {name} — {value}/день",
                callback_data=SettingsCB(action="newpace_set", value=str(value)).pack(),
            )
        ]
        for value, emoji, name in PACE_OPTIONS
    ]
    rows.append(
        [InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="push_open").pack())]
    )
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
            [_back_to_settings_button(), home_button()],
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
    rows.append([_back_to_settings_button(), home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
