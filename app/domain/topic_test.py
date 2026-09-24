"""Checking whether a passed topic is still known.

Ordinary practice runs with support: three attempts, a hint, and the options
visible for as long as the assisted mode lasts. That is the right shape for
learning and the wrong shape for measuring — a topic passed with help has not
been shown to be usable without it.

The test is the same sentences under different rules: one attempt, no hint, ten
in a row. It is the only place a session format is used, and it is used here
because "in a row, unaided" is the property being measured. Spreading these ten
across a day would restore exactly the context the test is trying to remove.

It is not an optional screen. Polyglot has one and it reads as abandoned — an
exam nobody is sent to is an exam nobody opens. This arrives in the day's plan
like any other card, with a way to defer it to tomorrow.

Failing is not a punishment and not a reset. The topic simply gets more cards
in the coming days, and the next test comes later on different sentences —
retaking immediately would measure the ten sentences rather than the rule.
"""

from __future__ import annotations

import html

# Ten is a compromise. Fewer, and one unlucky sentence swings the verdict;
# more, and a check that is meant to be a five-minute interruption becomes a
# session people postpone. At a minute a sentence this is the upper end of what
# fits in a push bot at all.
TEST_SIZE = 10

# 8 of 10. Below this the topic is not gone, but it is no longer reliable, and
# it earns extra practice until it recovers.
PASS_CORRECT = 8

# How long until the next check, by how many in a row the topic has held. The
# shape is the same expanding schedule used for words, for the same reason:
# something recalled after a longer gap is more firmly held, and asking sooner
# than necessary spends a card that another topic needed.
_INTERVALS = (3, 7, 21, 60)
MAX_INTERVAL_DAYS = 120

# Never more than one in a day. Twenty-seven topics all asking to be checked
# would turn a day into an examination sitting, which is the fastest way to
# make someone stop opening the bot.
MAX_TESTS_PER_DAY = 1


def next_interval_days(held_streak: int) -> int:
    """Days until this topic is checked again.

    `held_streak` counts consecutive passes; a failure resets it, which brings
    the next check back in close rather than leaving a shaky topic unchecked
    for two months.
    """
    if held_streak <= 0:
        return _INTERVALS[0]
    if held_streak >= len(_INTERVALS):
        return MAX_INTERVAL_DAYS
    return _INTERVALS[held_streak]


def passed(correct: int) -> bool:
    return correct >= PASS_CORRECT


def render_offer(topic_title: str) -> str:
    """The card that asks whether now is a good time.

    Says the cost up front. A test that starts the moment it arrives is a trap
    when it lands mid-commute, and the learner's guess at how long it takes is
    what decides whether they start it at all.
    """
    return (
        f"📝 <b>Проверка: {html.escape(topic_title)}</b>\n\n"
        f"{TEST_SIZE} заданий подряд, одна попытка на каждое, подсказок не будет.\n"
        "Примерно пять минут.\n\n"
        "<i>Не сейчас — придёт завтра.</i>"
    )


def render_question(topic_title: str, ru: str, index: int, correct_so_far: int) -> str:
    """One question. Carries the running count so the learner is not answering
    into silence for five minutes."""
    return (
        f"📝 <b>{html.escape(topic_title)}</b> · {index + 1} / {TEST_SIZE}"
        f" · ✅ {correct_so_far}\n\n"
        f"{html.escape(ru.strip())}\n\n"
        "<i>Напиши по-английски.</i>"
    )


def render_result(
    topic_title: str,
    correct: int,
    mistakes: list[tuple[str, str, str]],
    next_in_days: int,
) -> str:
    """The verdict, and every sentence that went wrong.

    Mistakes are listed with what was written beside what was expected. A score
    alone tells the learner they are worse than they thought and nothing about
    why — and this message is the only place these ten sentences will ever be
    seen together.
    """
    verdict = "держится" if passed(correct) else "просело — вернём в практику"
    parts = [
        f"📝 <b>{html.escape(topic_title)}</b> — {correct} из {TEST_SIZE}",
        f"<i>{verdict}</i>",
    ]
    if mistakes:
        parts.append("")
        parts.append("<b>Ошибки:</b>")
        for ru, given, expected in mistakes:
            written = html.escape(given.strip()) if given.strip() else "—"
            parts.append(
                f"· {html.escape(ru.strip())}\n"
                f"  ты: <i>{written}</i>\n"
                f"  надо: <b>{html.escape(expected.strip())}</b>"
            )
    parts.append("")
    parts.append(f"<i>Следующая проверка через {next_in_days} дн.</i>")
    return "\n".join(parts)
