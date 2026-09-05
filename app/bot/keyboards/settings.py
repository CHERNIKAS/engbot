from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import NoopCB, SettingsCB
from app.bot.keyboards.common import home_button
from app.bot.texts import LEVEL_RETAKE, PACE_LABELS
from app.domain.pacing import PACE_OPTIONS, label_for
from app.domain.push import window_hours


def _back_to_settings_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="open").pack())


def level_screen_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=LEVEL_RETAKE, callback_data=SettingsCB(action="level_test").pack()
                )
            ],
            [_back_to_settings_button()],
        ]
    )


def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⚡ Темп обучения", callback_data=SettingsCB(action="pace").pack())],
        [InlineKeyboardButton(text="🔔 Пуш-обучение", callback_data=SettingsCB(action="push_open").pack())],
        [InlineKeyboardButton(text="🕐 Часовой пояс", callback_data=SettingsCB(action="tz_open").pack())],
        [InlineKeyboardButton(text="📏 Мой уровень", callback_data=SettingsCB(action="level").pack())],
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


def push_window_kb(ws: int, we: int, min_hours: int = 10) -> InlineKeyboardMarkup:
    """Direct-pick grid for the daily push window — tap a start hour, tap an end
    hour, save. Any hours, overnight allowed (e.g. 22→08). The pending pair rides
    in the callback data, so nothing persists until '✅ Сохранить' (which enforces
    the minimum). 3 taps total — no slow stepping."""

    def grid(values: range, selected: int, pair) -> list[list[InlineKeyboardButton]]:
        rows: list[list[InlineKeyboardButton]] = []
        cells = list(values)
        for i in range(0, len(cells), 6):
            row = []
            for h in cells[i : i + 6]:
                a, b = pair(h)
                label = f"·{h:02d}·" if h == selected else f"{h:02d}"
                row.append(
                    InlineKeyboardButton(
                        text=label,
                        callback_data=SettingsCB(action="push_win_set", value=f"w_{a}_{b}").pack(),
                    )
                )
            rows.append(row)
        return rows

    hours = window_hours(ws, we)
    overnight = 0 < we <= ws
    if hours < min_hours:
        info = f"⚠️ {hours} ч — нужно ≥ {min_hours} ч"
    else:
        info = f"ℹ️ Окно: {hours} ч" + (" · через ночь 🌙" if overnight else "")

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🌅 Начало (час)", callback_data=NoopCB(tag="ws").pack())]
    ]
    rows += grid(range(0, 24), ws, lambda h: (h, we))
    rows.append([InlineKeyboardButton(text="🌙 Конец (час)", callback_data=NoopCB(tag="we").pack())])
    rows += grid(range(1, 25), we, lambda h: (ws, h))
    rows.append([InlineKeyboardButton(text=info, callback_data=NoopCB(tag="i").pack())])
    rows.append(
        [InlineKeyboardButton(text="✅ Сохранить", callback_data=SettingsCB(action="push_win_set", value=f"sv_{ws}_{we}").pack())]
    )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data=SettingsCB(action="push_open").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)




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
