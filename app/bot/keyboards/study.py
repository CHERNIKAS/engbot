from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import DeleteCB, StudyCB
from app.bot.keyboards.common import home_button


def study_menu_kb() -> InlineKeyboardMarkup:
    """On-demand manual drill (separate from the always-on push). Labels say
    WHICH set each button trains, so it's clear at a glance."""
    rows = [
        [
            InlineKeyboardButton(
                text="🎯 Цель на сегодня",
                callback_data=StudyCB(action="start", scope="goal").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="📚 Повторить всё",
                callback_data=StudyCB(action="start", scope="all").pack(),
            ),
            InlineKeyboardButton(
                text="🩹 Работа над ошибками",
                callback_data=StudyCB(action="start", scope="weak").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🆕 Новые слова",
                callback_data=StudyCB(action="start", scope="new").pack(),
            ),
            InlineKeyboardButton(
                text="⚡ Быстро — 5 слов",
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


def study_now_kb() -> InlineKeyboardMarkup:
    """Single 'study now' button — used in reminder messages."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔥 Учить",
                    callback_data=StudyCB(action="start", scope="goal").pack(),
                )
            ]
        ]
    )
