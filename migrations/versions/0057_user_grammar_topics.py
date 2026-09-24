"""Extend the per-topic row the constructor needs.

`user_grammar_topics` already existed to remember that a rule card had been
shown. The constructor needs three more things on the same row, and they belong
together — this is a learner's standing in one topic, not two unrelated facts.

`score` is the decaying accuracy shown as the 0–5 figure. It lives here rather
than being derived from the per-exercise rows because it has to be able to
fall: an average over per-item progress only ever climbs, which is how a topic
passed in March would still read as passed in September.

`typing` is the mode. A topic starts assisted — tap the pieces — and switches
to free typing once the score says the support has stopped teaching anything.
It is a ratchet: without that, the harder mode would drop the score back under
the threshold and bounce the learner between modes forever.

`recent` holds the last handful of phrase ids. Preferring what has not just
been seen is the difference between practising a rule and memorising five
sentences, and keeping it here avoids a per-phrase-per-user table whose only
job would be one timestamp.

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("score", sa.Float(), "0"),
    ("answered", sa.Integer(), "0"),
    # Consecutive passed checks. Drives the expanding interval between them,
    # and resets on a failure so a shaky topic is asked again soon rather than
    # left for two months.
    ("held_streak", sa.Integer(), "0"),
)


def upgrade() -> None:
    for name, type_, default in _COLUMNS:
        op.add_column(
            "user_grammar_topics",
            sa.Column(name, type_, nullable=False, server_default=default),
        )
    op.add_column(
        "user_grammar_topics",
        sa.Column("typing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user_grammar_topics",
        sa.Column("recent", JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "user_grammar_topics",
        sa.Column("passed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # When the topic was last checked, and when it is due again. Stored rather
    # than derived: the interval depends on the streak at the time, so
    # recomputing it later would move a due date that was already promised.
    op.add_column(
        "user_grammar_topics",
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_grammar_topics",
        sa.Column("test_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    # "Which topic is being learned" is asked on every grammar card.
    op.create_index(
        "ix_user_grammar_topics_active",
        "user_grammar_topics",
        ["user_id", "passed_at"],
    )
    # "Is any topic due for a check today" runs once per plan composition.
    op.create_index(
        "ix_user_grammar_topics_test_due",
        "user_grammar_topics",
        ["user_id", "test_due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_grammar_topics_test_due", table_name="user_grammar_topics")
    op.drop_index("ix_user_grammar_topics_active", table_name="user_grammar_topics")
    for name in (
        "test_due_at", "tested_at", "passed_at", "recent", "typing",
        "held_streak", "answered", "score",
    ):
        op.drop_column("user_grammar_topics", name)
