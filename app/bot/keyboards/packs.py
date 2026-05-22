from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.common import home_button

PACK_PAGE_SIZE = 8

# A lightweight row cached in Redis: (pack_id, title, words_count, learned_pct).
PackRow = tuple[int, str, int, int]


def pack_browser_kb(
    rows_in: list[PackRow],
    selected: set[int],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """ReWord-style checklist: each pack shows count + learned %, tap toggles it.
    Takes pre-computed rows (cached) so toggling never re-hits the DB."""
    rows: list[list[InlineKeyboardButton]] = []
    for pid, title, wc, pct in rows_in:
        mark = "✅" if pid in selected else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {title} · {wc} · {pct}%",
                    callback_data=PacksCB(action="toggle", pack_id=pid, page=page).pack(),
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀️", callback_data=PacksCB(action="page", page=page - 1).pack())
        )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(text="▶️", callback_data=PacksCB(action="page", page=page + 1).pack())
        )
    if nav:
        rows.append(nav)

    if selected:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"➕ Добавить выбранные ({len(selected)})",
                    callback_data=PacksCB(action="add").pack(),
                )
            ]
        )
        rows.append(
            [InlineKeyboardButton(text="🔄 Сбросить", callback_data=PacksCB(action="reset").pack())]
        )
    rows.append(
        [
            InlineKeyboardButton(text="↩️ Группы", callback_data=PacksCB(action="menu").pack()),
            home_button(),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


_GROUP_EMOJI = {"Уровни": "🎯", "Грамматика": "🔤", "Темы": "🗂", "Фразы": "💬", "Экзамены": "🎓"}


def pack_groups_kb(groups: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    """Top level of the pack browser: pick a group (category)."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{_GROUP_EMOJI.get(cat, '📦')} {cat} ({count})",
                callback_data=PacksCB(action="group", category=cat).pack(),
            )
        ]
        for cat, count in groups
    ]
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
