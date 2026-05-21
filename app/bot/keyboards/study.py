from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import DeleteCB, StudyCB
from app.bot.keyboards.common import home_button


def study_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🎯 Сегодняшняя цель",
                callback_data=StudyCB(action="start", scope="goal").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="📚 Все слова",
                callback_data=StudyCB(action="start", scope="all").pack(),
            ),
            InlineKeyboardButton(
                text="🔥 Слабые",
                callback_data=StudyCB(action="start", scope="weak").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🆕 Новые",
                callback_data=StudyCB(action="start", scope="new").pack(),
            ),
            InlineKeyboardButton(
                text="⚡ Быстрая",
                callback_data=StudyCB(action="start", scope="quick").pack(),
            ),
        ],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_card_kb(options: list[str], version: str, user_word_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, opt in enumerate(options):
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt[:60],
                    callback_data=StudyCB(action="answer", answer=f"q{idx}", v=version).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=DeleteCB(action="ask", user_word_id=user_word_id, flow="st").pack(),
            ),
            InlineKeyboardButton(
                text="🛑 Завершить",
                callback_data=StudyCB(action="finish", v=version).pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def typing_card_kb(version: str, user_word_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="💡 Подсказка",
                callback_data=StudyCB(action="hint", v=version).pack(),
            ),
            InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data=StudyCB(action="skip", v=version).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=DeleteCB(action="ask", user_word_id=user_word_id, flow="st").pack(),
            ),
            InlineKeyboardButton(
                text="🛑 Завершить",
                callback_data=StudyCB(action="finish", v=version).pack(),
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def finished_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
