from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bot.callbacks.schema import CourseCB, MainMenuCB, SearchCB
from app.bot.keyboards.common import home_button
from app.bot.texts import (
    BTN_COLLECTIONS,
    BTN_GRAMMAR,
    BTN_LESSON,
    BTN_LESSON_END,
    BTN_MY_WORDS,
    BTN_PROGRESS,
    BTN_SETTINGS,
    BTN_TODAY,
    MENU_PLACEHOLDER,
)


def main_menu_reply_kb() -> ReplyKeyboardMarkup:
    """Bottom navigation menu.

    ``is_persistent`` is intentionally left False so Telegram shows its native
    collapse (⌄) icon in the input field — the user hides/expands the keyboard
    themselves, no custom button needed.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            # Collections left the menu and moved inside «Мой словарь». In v2
            # the bot stocks the vocabulary itself: 448 of the last 497 words
            # arrived through `_top_up`, and the only pack anyone picks by hand
            # is a narrow one — 17 words across three learners. A top-level
            # button for that competes with the five things people do daily.
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_MY_WORDS)],
            [KeyboardButton(text=BTN_GRAMMAR), KeyboardButton(text=BTN_PROGRESS)],
            [KeyboardButton(text=BTN_LESSON), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder=MENU_PLACEHOLDER,
    )


def lesson_reply_kb() -> ReplyKeyboardMarkup:
    """The bottom keyboard while a lesson runs: one way out. The menu comes
    back with the message that ends the lesson."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_LESSON_END)]],
        resize_keyboard=True,
        input_field_placeholder="Ответ — сюда ✍️",
    )


def words_menu_kb() -> InlineKeyboardMarkup:
    """The "🗂 Настройки слов" submenu — everything about building your vocabulary:
    the guided course, your words, adding/importing, and ready-made packs."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎓 Курс — учись по плану", callback_data=CourseCB(action="open").pack())],
            [
                InlineKeyboardButton(text="📚 Мои слова", callback_data=MainMenuCB(section="words").pack()),
                InlineKeyboardButton(text="🔎 Поиск", callback_data=SearchCB(action="open").pack()),
            ],
            # TXT import is hidden rather than removed: it ran twice in sixty
            # days, and a file upload is a lot of surface for that. The handler
            # still works for anyone who sends a .txt, so nothing is lost.
            [InlineKeyboardButton(text="➕ Добавить слова", callback_data=MainMenuCB(section="add").pack())],
            [InlineKeyboardButton(text="📦 Готовые паки", callback_data=MainMenuCB(section="packs").pack())],
            [home_button()],
        ]
    )


# NOTE: the old inline `main_menu_kb` (a full inline main menu with a track
# switcher) was removed — navigation is the persistent bottom reply-keyboard
# (`main_menu_reply_kb`) plus the "🗂 Слова" submenu (`words_menu_kb`). Its
# `section` values progress/settings/track had no handlers.
