"""Straighten the to be grid — its columns did not line up.

0065 laid every topic out as a monospace grid, and in one of them the widest
label pushed its column out: «you/we/they are You are ready» sat half a line to
the right of the rows above it. A grid that does not line up is just text with
extra spaces, and this is the second topic a learner meets.

Split into a column of forms and a column of sentences, the way Present Simple
does it.

Revision ID: 0066
Revises: 0065
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

NEW = """🔹 <b>to be</b> — быть, являться, находиться.

<pre>I             am
he / she / it is
you/we/they   are

 +   I am ready
 −   He isn't ready
 ?   Are you ready?</pre>

⚠️ У <b>to be</b> нет do/does: отрицание и вопрос делает он сам."""

OLD = """🔹 <b>to be</b> — быть, являться, находиться.

<pre>I        am    I am ready
he/she/it is    He is ready
you/we/they are You are ready

 −   I am not / He isn't
 ?   Are you ready?</pre>

⚠️ У <b>to be</b> нет do/does: отрицание и вопрос делает он сам."""


def _set(rule: str) -> None:
    op.get_bind().execute(
        sa.text("UPDATE grammar_topics SET rule = :rule WHERE slug = :slug"),
        {"rule": rule, "slug": "verb_to_be"},
    )


def upgrade() -> None:
    _set(NEW)


def downgrade() -> None:
    _set(OLD)
