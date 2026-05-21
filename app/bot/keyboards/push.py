from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PushCB


def push_card_kb(options: list[str], uw_id: int) -> InlineKeyboardMarkup:
    """Single quiz card delivered as a push: pick the translation."""
    rows = [
        [
            InlineKeyboardButton(
                text=opt[:60],
                callback_data=PushCB(action="ans", uw_id=uw_id, idx=i).pack(),
            )
        ]
        for i, opt in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_schedule_prompt_kb() -> InlineKeyboardMarkup:
    """Daily 'keep or change schedule?' prompt. Both buttons use the universal
    'pu' prefix so they work in any interaction state."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оставить", callback_data=PushCB(action="keep_schedule").pack())],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data=PushCB(action="open_window").pack())],
        ]
    )
