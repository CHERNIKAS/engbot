from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import PushCB
from app.domain.enums import WordStatus

SNOOZE_LABELS: dict[int, str] = {3: "3 дня", 7: "неделю", 30: "месяц", 45: "полтора месяца"}

# «Не учить сейчас» parks a word being learned for a good while — it comes back
# on its own, no archive, no progress lost.
NOT_NOW_DAYS = 45


# One name per action. "Я это знаю" and "Уже уверенно знаю" were two labels on
# the same behaviour once the first one started crediting the word.
KNOW_LABEL = "✅ Я это знаю"
REMOVE_LABEL = "🙈 Убрать из обучения"


def push_card_kb(options: list[str], uw_id: int, status: str) -> InlineKeyboardMarkup:
    """A quiz card delivered as a push: answer buttons + per-status controls.

    Every status offers the same two escapes under different names only where
    they mean different things: "I know this" credits the word, "remove" drops
    it with no credit. A mastered word has nothing left to claim, so it gets
    snooze instead.
    """
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=opt[:60], callback_data=PushCB(action="ans", uw_id=uw_id, idx=i).pack())]
        for i, opt in enumerate(options)
    ]

    if status == WordStatus.NEW.value:
        rows.append(
            [InlineKeyboardButton(text=KNOW_LABEL, callback_data=PushCB(action="master", uw_id=uw_id).pack())]
        )
        # A new word can be unwanted without being known. Until "I know this"
        # started crediting the word, it doubled as the remove button and this
        # gap didn't exist.
        rows.append(
            [InlineKeyboardButton(text=REMOVE_LABEL, callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
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
            [InlineKeyboardButton(text=REMOVE_LABEL, callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
        )
    else:  # LEARNING / REVIEW
        rows.append(
            [InlineKeyboardButton(text=KNOW_LABEL, callback_data=PushCB(action="master", uw_id=uw_id).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text="⏸ Не учить сейчас", callback_data=PushCB(action="snooze", uw_id=uw_id, days=NOT_NOW_DAYS).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text=REMOVE_LABEL, callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def push_cloze_card_kb(uw_id: int, status: str) -> InlineKeyboardMarkup:
    """A cloze card is answered by TYPING the word, so no answer buttons — just
    a give-up button + the same per-status controls as a normal word card."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🤷 Не помню", callback_data=PushCB(action="giveup", uw_id=uw_id).pack())]
    ]
    if status == WordStatus.MASTERED.value:
        rows.append(
            [
                InlineKeyboardButton(text="😴 3 дня", callback_data=PushCB(action="snooze", uw_id=uw_id, days=3).pack()),
                InlineKeyboardButton(text="😴 неделя", callback_data=PushCB(action="snooze", uw_id=uw_id, days=7).pack()),
                InlineKeyboardButton(text="😴 месяц", callback_data=PushCB(action="snooze", uw_id=uw_id, days=30).pack()),
            ]
        )
    else:  # LEARNING / REVIEW
        rows.append(
            [InlineKeyboardButton(text=KNOW_LABEL, callback_data=PushCB(action="master", uw_id=uw_id).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text="⏸ Не учить сейчас", callback_data=PushCB(action="snooze", uw_id=uw_id, days=NOT_NOW_DAYS).pack())]
        )
    rows.append(
        [InlineKeyboardButton(text=REMOVE_LABEL, callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
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


def push_leech_kb(uw_id: int) -> InlineKeyboardMarkup:
    """Offered after a word is missed too many times in a row: postpone it for a
    week (frees its slot, auto-returns) or keep drilling it."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="😴 Отложить на неделю", callback_data=PushCB(action="leech_park", uw_id=uw_id).pack())],
            [InlineKeyboardButton(text="💪 Оставить — дожму", callback_data=PushCB(action="leech_keep", uw_id=uw_id).pack())],
        ]
    )


