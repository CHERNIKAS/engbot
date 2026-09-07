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


def push_window_kb(ws: int, we: int, min_hours: int, step: str = "ws") -> InlineKeyboardMarkup:
    """One grid at a time for the daily push window: pick the start hour, then
    the end hour, then save. Overnight is allowed (e.g. 22->08); nothing is
    persisted until 'Save', which enforces the minimum.

    It used to show BOTH grids stacked, and that was the bug users hit: the two
    are visually identical and every hour appears in each of them, so "21" in
    the start grid looks exactly like "21" in the end grid. People tapped their
    start hour and then their end hour in the same grid, and watched their first
    choice get replaced -- "it picks one or the other". Worse, the second grid's
    last row sat below the fold behind the message box, so the hours most likely
    wanted for an end (19-24) were the hardest to even reach.

    One grid can only mean one thing, and it fits on screen.
    """
    on_end = step == "we"
    values = range(1, 25) if on_end else range(0, 24)
    selected = we if on_end else ws
    # A tap on the end grid stays on the end grid ("e"); a tap on the start grid
    # advances to it ("w"), so the common path is start -> end -> save.
    op = "e" if on_end else "w"

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=("🌙 До скольки?" if on_end else "🌅 Во сколько начинать?"),
                callback_data=NoopCB(tag="hdr").pack(),
            )
        ]
    ]
    cells = list(values)
    for i in range(0, len(cells), 6):
        row = []
        for h in cells[i : i + 6]:
            a, b = (ws, h) if on_end else (h, we)
            row.append(
                InlineKeyboardButton(
                    text=(f"·{h:02d}·" if h == selected else f"{h:02d}"),
                    callback_data=SettingsCB(action="push_win_set", value=f"{op}_{a}_{b}").pack(),
                )
            )
        rows.append(row)

    hours = window_hours(ws, we)
    overnight = 0 < we <= ws
    if on_end:
        if hours < min_hours:
            info = f"⚠️ {ws:02d}:00 → {we:02d}:00 · {hours} ч — нужно ≥ {min_hours} ч"
        else:
            info = f"ℹ️ {ws:02d}:00 → {we:02d}:00 · {hours} ч" + (" · через ночь 🌙" if overnight else "")
        rows.append([InlineKeyboardButton(text=info, callback_data=NoopCB(tag="i").pack())])
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Сохранить",
                    callback_data=SettingsCB(action="push_win_set", value=f"sv_{ws}_{we}").pack(),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"⬅️ Начало: {ws:02d}:00",
                    callback_data=SettingsCB(action="push_win_set", value=f"b_{ws}_{we}").pack(),
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"➡️ Дальше — конец ({we:02d}:00)",
                    callback_data=SettingsCB(action="push_win_set", value=f"w_{ws}_{we}").pack(),
                )
            ]
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
