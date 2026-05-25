"""clearer grammar rules: spell out the subject→form mapping

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-23

Several rules only showed one case (e.g. Present Simple showed "he/she/it +s" but
not "I/you/we/they → base form"), so an exercise like "They ___ in London" (live)
was confusing. Rewrite the tense rules to spell out which subject takes which
form, with examples. Content-only; reversible (restores the old text).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


# (slug, new_rule, old_rule)
RULES: list[tuple[str, str, str]] = [
    (
        "tense_present_simple",
        (
            "🟢 <b>Present Simple</b> — регулярные действия, привычки, факты.\n"
            "• I / you / we / they → <b>базовая форма</b>: They <b>live</b>.\n"
            "• he / she / it → <b>+s/-es</b>: She <b>lives</b>.\n"
            "Пример: I work, but she work<b>s</b>."
        ),
        (
            "🟢 <b>Present Simple</b> — регулярные действия, привычки и факты.\n"
            "В 3-м лице ед. ч. (he/she/it) к глаголу добавляем <b>-s/-es</b>:\n"
            "I work → He work<b>s</b>."
        ),
    ),
    (
        "tense_present_continuous",
        (
            "🔵 <b>Present Continuous</b> — происходит прямо сейчас. <b>be + V-ing</b>:\n"
            "• I → <b>am</b> (I am reading)\n"
            "• he / she / it → <b>is</b> (she is cooking)\n"
            "• you / we / they → <b>are</b> (they are playing)"
        ),
        (
            "🔵 <b>Present Continuous</b> — действие происходит <b>прямо сейчас</b>.\n"
            "Формула: <b>am/is/are + V-ing</b>.\n"
            "Look! She <b>is running</b>."
        ),
    ),
    (
        "tense_past_simple",
        (
            "🟠 <b>Past Simple</b> — завершённые действия в прошлом.\n"
            "• Правильные глаголы: <b>+ed</b> (play → played).\n"
            "• Неправильные — особые формы (go → went, write → wrote).\n"
            "• <b>to be</b>: I/he/she/it → <b>was</b>, you/we/they → <b>were</b>."
        ),
        (
            "🟠 <b>Past Simple</b> — завершённые действия в прошлом.\n"
            "Правильные глаголы: <b>+ed</b> (play → played).\n"
            "Неправильные — особые формы (go → went)."
        ),
    ),
    (
        "future_going_to",
        (
            "🗓 <b>to be going to</b> — планы и очевидное будущее. <b>be going to + глагол</b>:\n"
            "• I → <b>am going to</b>\n"
            "• he / she / it → <b>is going to</b>\n"
            "• you / we / they → <b>are going to</b>\n"
            "Пример: I'm going to travel."
        ),
        (
            "🗓 <b>to be going to</b> — планы и очевидное будущее. <b>am/is/are going to</b> + "
            "глагол. I'm going to travel."
        ),
    ),
    (
        "present_perfect",
        (
            "✅ <b>Present Perfect</b> — действие связано с настоящим (опыт, результат, «уже/ещё»). "
            "<b>have/has + 3-я форма</b>:\n"
            "• he / she / it → <b>has</b> (she has finished)\n"
            "• I / you / we / they → <b>have</b> (I have seen it)"
        ),
        (
            "✅ <b>Present Perfect</b> (have/has + V3) — действие связано с настоящим: опыт, "
            "результат, «уже/ещё». I <b>have seen</b> it."
        ),
    ),
    (
        "past_continuous",
        (
            "⏳ <b>Past Continuous</b> — действие шло в момент в прошлом. <b>was/were + V-ing</b>:\n"
            "• I / he / she / it → <b>was</b> (I was reading)\n"
            "• you / we / they → <b>were</b> (they were playing)"
        ),
        (
            "⏳ <b>Past Continuous</b> (was/were + V-ing) — действие шло в момент в прошлом. "
            "I <b>was reading</b> when he called."
        ),
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text("UPDATE grammar_topics SET rule = :rule WHERE slug = :slug")
    for slug, new_rule, _old in RULES:
        conn.execute(stmt, {"rule": new_rule, "slug": slug})


def downgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text("UPDATE grammar_topics SET rule = :rule WHERE slug = :slug")
    for slug, _new, old_rule in RULES:
        conn.execute(stmt, {"rule": old_rule, "slug": slug})
