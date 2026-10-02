"""Rewrite the Present Simple rule as a table the learner can read mid-sentence.

The rule was three lines of prose, pushed once when the topic opened and marked
seen. For the learner who raised this it was shown on 23 May; the constructor
arrived in September, and by then the grammar he was being asked to apply sat
five months up the chat. «В угадайку играть?» was the fair question.

Prose is also the wrong shape. The method this format borrows from teaches a
tense as a grid — person against affirmative, negative and question — because
the thing a Russian speaker gets wrong is not the meaning of Present Simple but
which cell to stand in. A grid shows the -s moving to `does`; a sentence about
it does not.

Laid out vertically rather than as a wide table: a phone shows about thirty
monospace characters before it wraps, and a wrapped table is worse than none.

This is the pattern for the other twenty-nine topics.

Revision ID: 0064
Revises: 0063
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

NEW_RULE = """🟢 <b>Present Simple</b> — обычное, регулярное, привычное.

<pre>I / you / we / they
 +   I work
 −   I don't work
 ?   Do I work?

he / she / it
 +   He work<b>s</b>
 −   He doesn't work
 ?   Does he work?</pre>

⚠️ <b>-s</b> есть только в утверждении у he/she/it.
В отрицании и вопросе его забирает <b>does</b>."""

OLD_RULE = """🟢 <b>Present Simple</b> — регулярные действия, привычки, факты.
• I / you / we / they → <b>базовая форма</b>: They <b>live</b>.
• he / she / it → <b>+s/-es</b>: She <b>lives</b>.
Пример: I work, but she work<b>s</b>."""


def _set(rule: str) -> None:
    op.get_bind().execute(
        sa.text("UPDATE grammar_topics SET rule = :rule WHERE slug = :slug"),
        {"rule": rule, "slug": "tense_present_simple"},
    )


def upgrade() -> None:
    _set(NEW_RULE)


def downgrade() -> None:
    _set(OLD_RULE)
