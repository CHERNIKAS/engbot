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
# Every postponement is called the same thing and wears the same face. It used
# to be "⏸ Не учить сейчас" next to "😴 3 дня" — one action, two vocabularies,
# and the long one didn't say how long it actually was.
# The duration lives in the confirmation, not the button: "Отложить на полтора
# месяца" was the longest label on a card that already carries three ways to
# put a word down.
SNOOZE_LONG_LABEL = "😴 Отложить надолго"
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
                InlineKeyboardButton(text="😴 На 3 дня", callback_data=PushCB(action="snooze", uw_id=uw_id, days=3).pack()),
                InlineKeyboardButton(text="😴 На неделю", callback_data=PushCB(action="snooze", uw_id=uw_id, days=7).pack()),
                InlineKeyboardButton(text="😴 На месяц", callback_data=PushCB(action="snooze", uw_id=uw_id, days=30).pack()),
            ]
        )
        rows.append(
            [InlineKeyboardButton(text=SNOOZE_LONG_LABEL, callback_data=PushCB(action="snooze", uw_id=uw_id, days=NOT_NOW_DAYS).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text=REMOVE_LABEL, callback_data=PushCB(action="hide", uw_id=uw_id).pack())]
        )
    else:  # LEARNING / REVIEW
        rows.append(
            [InlineKeyboardButton(text=KNOW_LABEL, callback_data=PushCB(action="master", uw_id=uw_id).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text=SNOOZE_LONG_LABEL, callback_data=PushCB(action="snooze", uw_id=uw_id, days=NOT_NOW_DAYS).pack())]
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
                InlineKeyboardButton(text="😴 На 3 дня", callback_data=PushCB(action="snooze", uw_id=uw_id, days=3).pack()),
                InlineKeyboardButton(text="😴 На неделю", callback_data=PushCB(action="snooze", uw_id=uw_id, days=7).pack()),
                InlineKeyboardButton(text="😴 На месяц", callback_data=PushCB(action="snooze", uw_id=uw_id, days=30).pack()),
            ]
        )
    else:  # LEARNING / REVIEW
        rows.append(
            [InlineKeyboardButton(text=KNOW_LABEL, callback_data=PushCB(action="master", uw_id=uw_id).pack())]
        )
        rows.append(
            [InlineKeyboardButton(text=SNOOZE_LONG_LABEL, callback_data=PushCB(action="snooze", uw_id=uw_id, days=NOT_NOW_DAYS).pack())]
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




def constructor_slots_kb(options: list[str], phrase_id: int, can_undo: bool) -> InlineKeyboardMarkup:
    """The assisted mode: the current slot's choices, two to a row.

    Only the slot index is missing from the callback, and deliberately — it is
    already known from how many pieces the learner has chosen. Putting it in
    would spend bytes from the 64-byte callback budget to re-state something
    the server cannot disagree about.

    «Ой, ошибся» appears only once there is something to take back; an inert
    button teaches the learner to distrust the ones next to it.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(options), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt[:60],
                    callback_data=PushCB(action="slot", uw_id=phrase_id, idx=i + j).pack(),
                )
                for j, opt in enumerate(options[i : i + 2])
            ]
        )
    tail = [
        InlineKeyboardButton(
            text="💡 Подсказка", callback_data=PushCB(action="phint", uw_id=phrase_id).pack()
        ),
        # The rule was pushed once, when the topic opened, and scrolled away
        # within the hour. A method built on a table needs the table in reach
        # while the sentence is being built, not five months up the chat.
        InlineKeyboardButton(
            text="📖 Правило", callback_data=PushCB(action="prule", uw_id=phrase_id).pack()
        ),
    ]
    if can_undo:
        tail.insert(
            0,
            InlineKeyboardButton(
                text="↩️ Ой, ошибся",
                callback_data=PushCB(action="pundo", uw_id=phrase_id).pack(),
            ),
        )
    rows.append(tail)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def constructor_typing_kb(phrase_id: int) -> InlineKeyboardMarkup:
    """The typing mode: no answer buttons at all — that is the point of it.

    «Не помню» is the honest way out. Without it the only exits are typing
    something wrong on purpose or ignoring the card, and an ignored card is
    the one thing the plan cannot tell apart from being busy.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💡 Подсказка",
                    callback_data=PushCB(action="phint", uw_id=phrase_id).pack(),
                ),
                InlineKeyboardButton(
                    text="📖 Правило",
                    callback_data=PushCB(action="prule", uw_id=phrase_id).pack(),
                ),
                InlineKeyboardButton(
                    text="🤷 Не помню",
                    callback_data=PushCB(action="pgiveup", uw_id=phrase_id).pack(),
                ),
            ]
        ]
    )


def triage_kb(rows: list[tuple[int, str]], done_label: str) -> InlineKeyboardMarkup:
    """The batch triage screen: one word per row, plus «Готово».

    One per row rather than two because the label carries the translation, and
    a two-column layout truncates it to the point where the learner is deciding
    about a word they cannot read.

    `rows` is (user_word_id, label) — the id is what the toggle addresses, so
    a word whose label changes between renders still toggles the same row.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=PushCB(action="trg", uw_id=uw_id).pack(),
            )
        ]
        for uw_id, label in rows
    ]
    keyboard.append(
        [InlineKeyboardButton(text=done_label, callback_data=PushCB(action="trgok").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def test_offer_kb(topic_id: int) -> InlineKeyboardMarkup:
    """Start now or push it to tomorrow.

    Deferring has to be one tap and cost nothing. A check that begins the
    moment it lands is a trap when it lands mid-commute, and a trap gets
    ignored rather than postponed — which loses the measurement entirely.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Начать", callback_data=PushCB(action="tstart", uw_id=topic_id).pack()
                ),
                InlineKeyboardButton(
                    text="🕐 Завтра", callback_data=PushCB(action="tlater", uw_id=topic_id).pack()
                ),
            ]
        ]
    )
