from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PushCB
from app.domain.enums import WordStatus

SNOOZE_LABELS: dict[int, str] = {3: "3 дня", 7: "неделю", 30: "месяц"}


def push_card_kb(options: list[str], uw_id: int, status: str) -> InlineKeyboardMarkup:
    """A quiz card delivered as a push: answer buttons + per-status controls.
    - brand-new word: "не показывать, я знаю"
    - word being learned: "перестать показывать"
    - mastered word: snooze (3d/week/month) + "перестать показывать"
    """
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=opt[:60], callback_data=PushCB(action="ans", uw_id=uw_id, idx=i).pack())]
        for i, opt in enumerate(options)
    ]

    if status == WordStatus.NEW.value:
        rows.append(
            [InlineKeyboardButton(text="🙅 Не показывать — я знаю", callback_data=PushCB(action="know", uw_id=uw_id).pack())]
        )
    elif status == WordStatus.MASTERED.value:
        rows.append(
            [
                InlineKeyboardButton(text="😴 3 дня", callback_data=PushCB(action="snooze", uw_id=uw_id, days=3).pack()),
                InlineKeyboardButton(text="😴 неделя", callback_data=PushCB(action="snooze", uw_id=uw_id, days=7).pack()),
                InlineKeyboardButton(text="😴 месяц", callback_data=PushCB(action="snooze", uw_id=uw_id, days=30).pack()),
            ]
        )
        rows.append(
            [InlineKeyboardButton(text="🙈 Перестать показывать", callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
        )
    else:  # LEARNING / REVIEW
        rows.append(
            [InlineKeyboardButton(text="🙈 Перестать показывать", callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_grammar_card_kb(options: list[str], ugi_id: int) -> InlineKeyboardMarkup:
    """A grammar exercise card: answer buttons + a "📖 Правило" button so the
    user can read the rule instead of guessing. The answer callback reuses the
    universal 'ans' action; uw_id carries the user_grammar_item id and the
    handler routes by the inflight 'kind'."""
    rows = [
        [InlineKeyboardButton(text=opt[:60], callback_data=PushCB(action="ans", uw_id=ugi_id, idx=i).pack())]
        for i, opt in enumerate(options)
    ]
    rows.append(
        [InlineKeyboardButton(text="📖 Правило", callback_data=PushCB(action="rule", uw_id=ugi_id).pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_rule_kb() -> InlineKeyboardMarkup:
    """A grammar rule card — just an acknowledge button (no answer)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👌 Понятно", callback_data=PushCB(action="rule_ok").pack())]]
    )


