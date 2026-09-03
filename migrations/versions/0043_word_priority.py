"""Per-word "teach this first" flag.

Two of the eight users keep 60-68% of their vocabulary as words they added
themselves; the rest never add any. Ordering purely by level serves the second
group and quietly reshuffles the first group's list — someone importing
vocabulary for an exam next month gets it spread across levels instead of
taught.

Rather than guess which they meant, the bot asks after an import. A flagged
word jumps the queue; everything else is picked by level as before.

Revision ID: 0043
Revises: 0042
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_words",
        sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_words", "priority")
