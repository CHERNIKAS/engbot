"""Per-user CEFR level — the missing half of level-aware word selection.

0037 gave every word a level; without a level on the user there is still nothing
to compare it to. NULL is meaningful here and stays the default: it means "not
placed yet", which is what makes the onboarding placement test skippable and
re-runnable rather than a one-off value we'd have to guess at signup.

Revision ID: 0038
Revises: 0037
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("level", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "level")
