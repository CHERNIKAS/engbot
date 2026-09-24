"""How long an answer took, and whether the card had to be nudged.

Every number in the day-plan arithmetic — how many cards fit a day, how much
attention a plan costs — rests on how long one card takes. That was never
recorded: reviews store only `reviewed_at`, and the moment a card was sent
lived in Redis and died there. So the per-card cost could only be guessed.

`response_ms` closes that. `attempts` is what makes it usable: a card answered
on the first push measures attention, while one answered after two nudges
measures how long the phone sat face-down. Only attempts = 1 rows are a clean
sample, and without the column there is no way to tell them apart.

Both nullable — the answer paths that predate this simply leave them empty
rather than inventing a duration.

Revision ID: 0044
Revises: 0043
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_TABLES = ("word_reviews", "grammar_reviews")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("response_ms", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("attempts", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "attempts")
        op.drop_column(table, "response_ms")
