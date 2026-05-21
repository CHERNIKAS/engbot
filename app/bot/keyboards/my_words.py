from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import CategoryCB, DeleteCB, MainMenuCB, MyWordsCB
from app.bot.keyboards.common import home_button
from app.domain.models import Category


def categories_overview_kb(
    categories: list[Category],
    counts: dict[int | None, int],
    *,
    flow: str = "mw",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    total = sum(counts.values())
    uncategorized = counts.get(None, 0)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"📁 Все слова ({total})",
                callback_data=MyWordsCB(action="open", category_id=0).pack(),
            )
        ]
    )
    if uncategorized:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📁 Без категории ({uncategorized})",
                    callback_data=MyWordsCB(action="open", category_id=-1).pack(),
                )
            ]
        )

    for cat in categories:
        count = counts.get(cat.id, 0)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📁 {cat.name} ({count})",
                    callback_data=MyWordsCB(action="open", category_id=cat.id).pack(),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Новая категория",
                callback_data=CategoryCB(action="new", flow=flow).pack(),
            )
        ]
    )
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_words_kb(
    category_id: int,
    items: list[tuple[int, str]],  # (user_word_id, english)
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for uw_id, english in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=english,
                    callback_data=DeleteCB(action="ask", user_word_id=uw_id, flow="mw").pack(),
                )
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=MyWordsCB(action="open", category_id=category_id, page=page - 1).pack(),
            )
        )
    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=MyWordsCB(action="open", category_id=category_id, page=page + 1).pack(),
            )
        )
    if nav:
        rows.append(nav)

    if category_id != 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔥 Учить эту категорию",
                    callback_data=MyWordsCB(action="study_cat", category_id=category_id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить слова",
                callback_data=MainMenuCB(section="add").pack(),
            ),
            home_button(),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm_kb(user_word_id: int, flow: str, version: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=DeleteCB(
                        action="confirm", user_word_id=user_word_id, flow=flow, v=version
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="↩️ Нет",
                    callback_data=DeleteCB(
                        action="cancel", user_word_id=user_word_id, flow=flow, v=version
                    ).pack(),
                ),
            ]
        ]
    )
