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
    BTN_HELP,
    BTN_PROGRESS,
    BTN_SETTINGS,
    BTN_STUDY,
    BTN_WORDS,
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
            [KeyboardButton(text=BTN_WORDS), KeyboardButton(text=BTN_STUDY)],
            [KeyboardButton(text=BTN_PROGRESS), KeyboardButton(text=BTN_SETTINGS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder=MENU_PLACEHOLDER,
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
            [
                InlineKeyboardButton(text="➕ Добавить слова", callback_data=MainMenuCB(section="add").pack()),
                InlineKeyboardButton(text="📂 Импорт TXT", callback_data=MainMenuCB(section="import").pack()),
            ],
            [InlineKeyboardButton(text="📦 Готовые паки", callback_data=MainMenuCB(section="packs").pack())],
            [home_button()],
        ]
    )


# NOTE: the old inline `main_menu_kb` (a full inline main menu with a track
# switcher) was removed — navigation is the persistent bottom reply-keyboard
# (`main_menu_reply_kb`) plus the "🗂 Слова" submenu (`words_menu_kb`). Its
# `section` values progress/settings/track had no handlers.
