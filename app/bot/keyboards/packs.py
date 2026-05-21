from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.common import home_button
from app.domain.models import Pack

PACK_PAGE_SIZE = 8


def pack_browser_kb(
    packs: list[Pack],
    stats: dict[int, tuple[int, int]],
    selected: set[int],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """ReWord-style checklist: each pack shows count + learned %, tap toggles it."""
    rows: list[list[InlineKeyboardButton]] = []
    for p in packs:
        _owned, mastered = stats.get(p.id, (0, 0))
        pct = round(100 * mastered / p.words_count) if p.words_count else 0
        mark = "✅" if p.id in selected else "☑️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {p.title} · {p.words_count} · {pct}%",
                    callback_data=PacksCB(action="toggle", pack_id=p.id, page=page).pack(),
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
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
