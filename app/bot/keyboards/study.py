from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import DeleteCB, StudyCB
from app.bot.keyboards.common import home_button


def study_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🎯 Сегодняшняя цель",
                callback_data=StudyCB(action="start", mode="classic", scope="goal").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="📚 Все слова",
                callback_data=StudyCB(action="start", mode="classic", scope="all").pack(),
            ),
            InlineKeyboardButton(
                text="🔥 Слабые",
                callback_data=StudyCB(action="start", mode="classic", scope="weak").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🆕 Новые",
                callback_data=StudyCB(action="start", mode="classic", scope="new").pack(),
            ),
            InlineKeyboardButton(
                text="⚡ Быстрая",
                callback_data=StudyCB(action="start", mode="classic", scope="quick").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🧩 Quiz",
                callback_data=StudyCB(action="start", mode="quiz", scope="goal").pack(),
            ),
        ],
        [home_button()],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def classic_question_kb(user_word_id: int, version: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="👀 Показать перевод",
                callback_data=StudyCB(action="show_translation", v=version).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="💡 Пример",
                callback_data=StudyCB(action="example", v=version).pack(),
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


def classic_answer_kb(user_word_id: int, version: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="😵 Сложно",
                callback_data=StudyCB(action="answer", answer="hard", v=version).pack(),
            ),
            InlineKeyboardButton(
                text="🙂 Нормально",
                callback_data=StudyCB(action="answer", answer="normal", v=version).pack(),
            ),
            InlineKeyboardButton(
                text="😎 Легко",
                callback_data=StudyCB(action="answer", answer="easy", v=version).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="💡 Пример",
                callback_data=StudyCB(action="example", v=version).pack(),
            ),
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=DeleteCB(action="ask", user_word_id=user_word_id, flow="st").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🛑 Завершить",
                callback_data=StudyCB(action="finish", v=version).pack(),
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_kb(options: list[str], version: str, user_word_id: int) -> InlineKeyboardMarkup:
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


def finished_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
