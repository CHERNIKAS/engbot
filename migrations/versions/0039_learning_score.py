"""Weighted learning score + a count of typed answers.

`repetitions_count` treated a guessed four-option card and a typed answer as
the same event, so a word could reach "learned" without ever being written.
The score weights each answer by what it proves, and `production_count` is the
floor that guessing cannot climb.

Existing progress is converted rather than reset. The reps users already have
were earned under the old fixed ladder — recognition at 0-2, reverse at 3-4,
typed from 5 — so each rep is credited at the weight of the rung it was
actually answered on, and everything past the fifth counts as production.

Revision ID: 0039
Revises: 0038
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# Legacy ladder boundaries and weights these reps were earned under. Written as
# literals rather than bind parameters: the first cut passed them as params and
# the arithmetic silently collapsed — every row came out with the score equal to
# its production count instead of the weighted sum. Inline constants are checked
# by simply reading the SQL.
_BACKFILL = sa.text(
    """
    UPDATE user_words SET
      learning_score = ROUND((
          LEAST(repetitions_count, 3) * 0.5
        + GREATEST(LEAST(repetitions_count, 5) - 3, 0) * 0.8
        + GREATEST(repetitions_count - 5, 0) * 1.5
      )::numeric, 2),
      production_count = GREATEST(repetitions_count - 5, 0)
    """
)


def upgrade() -> None:
    op.add_column(
        "user_words",
        sa.Column("learning_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_words",
        sa.Column("production_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.get_bind().execute(_BACKFILL)


def downgrade() -> None:
    # repetitions_count was never touched, so the old rule still works as-is.
    op.drop_column("user_words", "production_count")
    op.drop_column("user_words", "learning_score")
