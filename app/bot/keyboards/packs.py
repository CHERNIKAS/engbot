from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.common import home_button

PACK_PAGE_SIZE = 8

# A row cached in Redis state: (pack_id, title, words_count, learned_pct, owned).
PackRow = tuple[int, str, int, int, int]


def pack_browser_kb(
    rows_in: list[PackRow],
    page: int,
    total_pages: int,
    course_managed: bool = False,
) -> InlineKeyboardMarkup:
    """Checklist where the mark reflects what's ACTUALLY in your learning:
    ✅ = added (you own all its words), ⬜ = not added. Tapping applies
    immediately (add, or ask-to-remove). Level packs under an active course are
    shown as 🎓 (managed by the course, not toggled here)."""
    rows: list[list[InlineKeyboardButton]] = []
    for pid, title, wc, pct, owned in rows_in:
        if course_managed:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🎓 {title} · {wc} · {pct}%",
                        callback_data=PacksCB(action="course_info").pack(),
                    )
                ]
            )
            continue
        mark = "✅" if wc > 0 and owned >= wc else "⬜"
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
        nav.append(InlineKeyboardButton(text="◀️", callback_data=PacksCB(action="page", page=page - 1).pack()))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=PacksCB(action="page", page=page + 1).pack()))
    if nav:
        rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(text="↩️ Группы", callback_data=PacksCB(action="menu").pack()),
            home_button(),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pack_remove_confirm_kb(pack_id: int, page: int, version: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, убрать", callback_data=PacksCB(action="rem_ok", pack_id=pack_id, page=page, v=version).pack())],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data=PacksCB(action="page", page=page).pack())],
        ]
    )


_GROUP_EMOJI = {"Уровни": "🎯", "Грамматика": "🔤", "Темы": "🗂", "Фразы": "💬", "Живой английский": "🗣", "Экзамены": "🎓"}


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
