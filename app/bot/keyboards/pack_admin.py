"""Keyboards for the pack admin. Reachable only via /packs_admin, never from a menu."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PackAdminCB
from app.domain.models import Pack
from app.services.pack_admin_service import AUTOFILL_CATEGORIES, KNOWN_CATEGORIES, index_of


def categories_kb(rows: list[tuple[str, int, int]]) -> InlineKeyboardMarkup:
    """One row per category: name, how many packs, how many are on."""
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"{name} · {active}/{total}"
                    + (" · автопополнение" if name in AUTOFILL_CATEGORIES else "")
                ),
                callback_data=PackAdminCB(action="list", cat=index_of(name)).pack(),
            )
        ]
        for name, total, active in rows
        if index_of(name) >= 0
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def packs_kb(category: str, packs: list[Pack]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if p.is_active else '⬜'} {p.position}. {p.title}"
                + ("" if p.origin == "migration" else " ✏️"),
                callback_data=PackAdminCB(action="open", pack_id=p.id).pack(),
            )
        ]
        for p in packs
    ]
    rows.append(
        [InlineKeyboardButton(text="↩️ Категории", callback_data=PackAdminCB(action="cats").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pack_kb(pack: Pack) -> InlineKeyboardMarkup:
    pid = pack.id
    rows = [
        [
            InlineKeyboardButton(
                text="⬜ Выключить" if pack.is_active else "✅ Включить",
                callback_data=PackAdminCB(action="toggle", pack_id=pid).pack(),
            )
        ],
        [
            InlineKeyboardButton(text="⬆️ Выше", callback_data=PackAdminCB(action="up", pack_id=pid).pack()),
            InlineKeyboardButton(text="⬇️ Ниже", callback_data=PackAdminCB(action="down", pack_id=pid).pack()),
        ],
        [
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=PackAdminCB(action="rename", pack_id=pid).pack()),
            InlineKeyboardButton(text="🗂 Категория", callback_data=PackAdminCB(action="cat", pack_id=pid).pack()),
        ],
    ]
    if pack.origin != "migration":
        # The escape hatch: a shipped fix skips admin-owned packs, so there has
        # to be a way to hand one back.
        rows.append(
            [
                InlineKeyboardButton(
                    text="↩️ Вернуть миграциям",
                    callback_data=PackAdminCB(action="reset", pack_id=pid).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="↩️ К списку",
                callback_data=PackAdminCB(action="list", cat=index_of(pack.category)).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_pick_kb(pack: Pack) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=("• " if name == pack.category else "")
                + name
                + ("" if name in AUTOFILL_CATEGORIES else " ⚠️"),
                callback_data=PackAdminCB(action="cat_set", cat=i, pack_id=pack.id).pack(),
            )
        ]
        for i, name in enumerate(KNOWN_CATEGORIES)
    ]
    rows.append(
        [InlineKeyboardButton(text="↩️ Назад", callback_data=PackAdminCB(action="open", pack_id=pack.id).pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
