"""The day's plan, stored so it can be held rather than regenerated.

Cards used to be drawn one at a time from a weighted lottery, which meant the
day had no shape: you could not be told what it contained, how long it was, or
whether you had finished. Prod showed what that cost — the bot could push ~56
cards into an evening window against ten answers, and nudged the rest until it
gave up on them.

The plan has to live in the database rather than in Redis with the other push
state, because it is explicitly allowed to outlive the day it was made for. An
unfinished plan is not replaced tomorrow: it is the same plan until it is
closed. A cache eviction in the middle of that would silently hand the learner
a different day, which is precisely the unpredictability being removed.

`items` holds the cards as `{kind, ref, done}`. Storing the composition rather
than recomputing it is the point — recomputing would let the plan shift under
the learner whenever the review queue moved.

Only one plan per user is open at a time; `closed_at` marks the end. Closed
rows are kept because the resize rule reads them: a week of closes grows the
plan, three misses shrink it, and both are counted from this history rather
than from a counter that could drift.

Revision ID: 0056
Revises: 0055
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "day_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("track", sa.String(length=8), nullable=False, server_default="en"),
        # What the plan was built to be, kept alongside the items so a resize
        # can be explained after the fact ("28 → 30") instead of inferred.
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("items", JSONB(), nullable=False, server_default="[]"),
        # The push-day the plan was opened for. The push day rolls at the start
        # of the user's window, not at midnight, so this is not always today's
        # calendar date — see push_service._push_day.
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Finding the open plan is the hottest read: every push tick does it.
    op.create_index(
        "ix_day_plans_user_open",
        "day_plans",
        ["user_id", "track", "closed_at"],
    )
    # At most one plan in flight per user and track. Enforced rather than
    # trusted: two open plans would make "yesterday's plan is today's plan"
    # ambiguous, and nothing downstream could recover from it.
    op.create_index(
        "uq_day_plans_one_open",
        "day_plans",
        ["user_id", "track"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_day_plans_one_open", table_name="day_plans")
    op.drop_index("ix_day_plans_user_open", table_name="day_plans")
    op.drop_table("day_plans")
