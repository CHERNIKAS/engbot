"""user_words: consecutive_wrong counter for leech detection.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-28

Tracks consecutive wrong answers per word (reset to 0 on any correct). When it
crosses the leech threshold the bot offers to postpone the word, so a single
impossible word can't permanently occupy a slot in the active pool.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_words",
        sa.Column("consecutive_wrong", sa.Integer(), nullable=False, server_default="0"),
    )
    # Drop the server_default now that existing rows are backfilled — the ORM
    # supplies 0 on insert.
    op.alter_column("user_words", "consecutive_wrong", server_default=None)


def downgrade() -> None:
    op.drop_column("user_words", "consecutive_wrong")
