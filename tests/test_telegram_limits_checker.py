"""The e2e fake Telegram refuses what the real one would — check the checker.

If `telegram_problems` let things through, every e2e scenario would pass while
real sends were being rejected; these pin that it does not.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tests.e2e.harness import telegram_problems


def _kb(data: str, text: str = "x") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)]])


def test_clean_message_passes():
    assert telegram_problems("<b>ok</b> <i>fine</i>", _kb("pu:ans:1:0:0"), "HTML") == []


def test_callback_data_is_measured_in_bytes_not_characters():
    # 40 Cyrillic letters are 80 bytes: under 64 characters, over the limit.
    assert telegram_problems("t", _kb("pk:group:" + "я" * 40), None)


def test_overlong_text_is_refused():
    assert telegram_problems("a" * 4097, None, None)


def test_unbalanced_or_unsupported_html_is_refused():
    assert telegram_problems("<b>open", None, "HTML")
    assert telegram_problems("<div>x</div>", None, "HTML")
    assert telegram_problems("<b><i>x</b></i>", None, "HTML")


def test_plain_text_is_not_parsed_as_html():
    assert telegram_problems("a < b and <c>", None, None) == []


def test_an_empty_button_label_is_refused():
    assert telegram_problems("t", _kb("pu:ans:1:0:0", text=" "), None)
