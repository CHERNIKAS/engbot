from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import CategoryCB, PacksCB
from app.bot.keyboards.common import cancel_button, home_button
from app.domain.models import Category, Pack


def pack_categories_kb(categories: list[str], selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        marker = "✅" if cat in selected else "☑️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker} {cat}",
                    callback_data=PacksCB(action="toggle_cat", category=cat).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="Сбросить", callback_data=PacksCB(action="reset_cats").pack()),
            InlineKeyboardButton(text="Продолжить ▶️", callback_data=PacksCB(action="list").pack()),
        ]
    )
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pack_list_kb(packs: list[Pack]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in packs:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{p.title} — {p.words_count} слов",
                    callback_data=PacksCB(action="preview", pack_id=p.id).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data=PacksCB(action="menu").pack())])
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pack_preview_kb(pack_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить пак", callback_data=PacksCB(action="add", pack_id=pack_id).pack())],
            [InlineKeyboardButton(text="↩️ Назад", callback_data=PacksCB(action="list").pack()), home_button()],
        ]
    )


def pack_add_category_kb(
    pack_id: int,
    categories: list[Category],
    version: str = "",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append(
        [
            InlineKeyboardButton(
                text="📁 Без категории",
                callback_data=CategoryCB(action="pick", category_id=0, flow="pk", v=version).pack(),
            )
        ]
    )
    for cat in categories:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📁 {cat.name}",
                    callback_data=CategoryCB(
                        action="pick", category_id=cat.id, flow="pk", v=version
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Новая категория",
                callback_data=CategoryCB(action="new", flow="pk").pack(),
            )
        ]
    )
    rows.append([cancel_button(), home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
