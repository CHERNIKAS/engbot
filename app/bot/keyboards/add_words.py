from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import AddWordsCB, CategoryCB, ImportCB, MainMenuCB
from app.bot.keyboards.common import cancel_button, home_button
from app.bot.texts import IMPORT_PRIORITY_ON
from app.domain.models import Category


def add_choose_category_kb(
    categories: list[Category],
    *,
    flow: str = "add",
    version: str = "",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append(
        [
            InlineKeyboardButton(
                text="📁 Без категории",
                callback_data=CategoryCB(action="pick", category_id=0, flow=flow, v=version).pack(),
            )
        ]
    )
    for cat in categories:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📁 {cat.name}",
                    callback_data=CategoryCB(
                        action="pick", category_id=cat.id, flow=flow, v=version
                    ).pack(),
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
    rows.append([cancel_button(), home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_add_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Учить сейчас", callback_data=MainMenuCB(section="study").pack())],
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data=AddWordsCB(action="start").pack())],
            [home_button()],
        ]
    )


def import_priority_kb() -> InlineKeyboardMarkup:
    """Offered right after an import: put this batch ahead of the level-ordered
    queue, or leave it to be mixed in like everything else."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=IMPORT_PRIORITY_ON,
                    callback_data=ImportCB(action="prioritise").pack(),
                )
            ],
            [InlineKeyboardButton(text="Подмешивать по уровню", callback_data=MainMenuCB(section="words").pack())],
        ]
    )
