from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import MyWordsCB, SearchCB
from app.bot.keyboards.common import home_button

_LABEL_MAX = 36


def _label(writing: str, translation: str | None) -> str:
    text = writing if not translation else f"{writing} — {translation}"
    if len(text) > _LABEL_MAX:
        text = text[: _LABEL_MAX - 1] + "…"
    return text


def search_results_kb(
    own: list[tuple[int, str, str | None]],
    catalog: list[tuple[int, str, str | None]],
) -> InlineKeyboardMarkup:
    """Search results: own words open their detail card, catalog words get a
    one-tap add. `own` rows are (user_word_id, writing, translation), `catalog`
    rows are (word_id, writing, translation)."""
    rows: list[list[InlineKeyboardButton]] = []
    for uw_id, writing, translation in own:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📗 {_label(writing, translation)}",
                    callback_data=MyWordsCB(action="word", user_word_id=uw_id).pack(),
                )
            ]
        )
    for word_id, writing, translation in catalog:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"➕ {_label(writing, translation)}",
                    callback_data=SearchCB(action="add", word_id=word_id).pack(),
                )
            ]
        )
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)
