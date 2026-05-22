"""push v2: mastery_score, archived, snooze_until on user_words

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-22

Adds per-word fields for the reworked push engine:
- mastery_score: 0–5 health score for mastered words (5.0 = fully learned).
- archived: word removed from all push rotation ("я знаю" / "перестать
  показывать"), restorable from the management menu.
- snooze_until: hide a mastered word from review until this time ("отложить").
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_words",
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_words",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user_words",
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_words_archived", "user_words", ["archived"])


def downgrade() -> None:
    op.drop_index("ix_user_words_archived", table_name="user_words")
    op.drop_column("user_words", "snooze_until")
    op.drop_column("user_words", "archived")
    op.drop_column("user_words", "mastery_score")
