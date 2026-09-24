"""What the day says when it is finished.

Shown only on closing the plan, and that condition is the whole point. A
summary that arrives every evening regardless is a status report; one that
arrives because the plan is done is the thing the plan was for. The bot
otherwise has no moment that means "that's it, well done" — the old lottery
simply went quiet, which reads as the bot losing interest rather than the
learner finishing.

It reports what was actually in the day rather than a fixed set of lines. A
day with no phrases in it should not print «💬 0 фраз»: a zero is noise, and a
list of zeroes makes the two real numbers harder to find.
"""

from __future__ import annotations

import html

from app.domain import day_plan as plan_rules

# Order the lines are printed in, and the label each kind gets. Repeats first
# because on most days they are the bulk of the work, and the learner should
# see the largest number they earned rather than hunt for it under the new
# words.
_LINES: tuple[tuple[str, str], ...] = (
    (plan_rules.REPEAT, "🔁 повторов"),
    (plan_rules.NEW_WORD, "🆕 новых слов"),
    (plan_rules.NEW_THEME_WORD, "🆕 слов по теме"),
    (plan_rules.PHRASE, "💬 фраз"),
    (plan_rules.GRAMMAR, "📖 грамматики"),
    (plan_rules.TRIAGE, "🗂 разбор темы"),
)


def render(
    *,
    counts: dict[str, int],
    streak_days: int = 0,
    topic_title: str = "",
    score_before: float | None = None,
    score_after: float | None = None,
    topic_passed: bool = False,
    test_line: str = "",
) -> str:
    """The closing message.

    `score_before` and `score_after` are the grammar topic's standing at the
    start and end of the day. Both are needed: a bare «4.1» says nothing about
    whether the day helped, and the point of showing it here is that it moved.
    """
    parts = ["✅ <b>План на сегодня закрыт</b>", ""]

    for kind, label in _LINES:
        n = counts.get(kind, 0)
        if n:
            parts.append(f"{label}: {n}")

    if topic_title and score_after is not None:
        from app.domain.constructor import stars

        line = f"\n📖 <b>{html.escape(topic_title)}</b> — {stars(score_after)}"
        if score_before is not None and stars(score_before) != stars(score_after):
            arrow = "↑" if score_after > score_before else "↓"
            line += f" {arrow} <i>(было {stars(score_before)})</i>"
        parts.append(line)

    if topic_passed and topic_title:
        parts.append(f"🎓 <b>{html.escape(topic_title)}</b> — тема сдана!")

    if test_line:
        parts.append("")
        parts.append(test_line)

    if streak_days > 1:
        # One day is not a streak. Announcing "🔥 серия 1 день" the first time
        # someone finishes makes the feature look like it is counting down.
        parts.append("")
        parts.append(f"🔥 Серия: {streak_days} {_days(streak_days)} подряд")

    return "\n".join(parts)


def _days(n: int) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"


def render_resized(old: int, new: int) -> str:
    """Said out loud when the plan changes size.

    A plan that silently grows looks broken — the learner notices the day got
    longer and has no reason given. Both directions are stated, and shrinking
    is phrased as the bot adjusting rather than as the learner falling behind.
    """
    if new > old:
        return f"\n\n<i>Держишь темп — добавляю пару карточек: {old} → {new}.</i>"
    return f"\n\n<i>Снижаю нагрузку: {old} → {new}. Вернём, когда войдёшь в ритм.</i>"
