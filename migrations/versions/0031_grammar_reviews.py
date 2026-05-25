"""grammar answer log (so daily-activity counts include grammar)

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-25

word_reviews has a NOT NULL FK to user_words, so grammar answers had nowhere to
be logged — the «сегодня X / goal» counter on 📊 Прогресс silently ignored every
grammar card. This adds a parallel grammar_reviews table; the push engine writes
one row per grammar answer, and the progress screen sums words + grammar.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grammar_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_grammar_item_id",
            sa.Integer(),
            sa.ForeignKey("user_grammar_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("track", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_grammar_reviews_user_track_date",
        "grammar_reviews",
        ["user_id", "track", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_grammar_reviews_user_track_date", table_name="grammar_reviews")
    op.drop_table("grammar_reviews")
