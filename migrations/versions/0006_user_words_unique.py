"""dedup user_words and enforce unique(user_id, word_id)

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-06

One word per user — moving a word between categories must not fragment its
spaced-repetition history. Existing duplicates are merged: for each (user_id,
word_id) group we keep the row with the most learning history (highest
repetitions_count, then most recent last_reviewed_at) and delete the rest.
"""
from __future__ import annotations

from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pick the "winner" row per (user_id, word_id) — most progress, most recent.
    # Delete every losing user_words row; ON DELETE CASCADE on word_reviews keeps refs sane.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, word_id
                    ORDER BY
                        repetitions_count DESC,
                        last_reviewed_at DESC NULLS LAST,
                        id ASC
                ) AS rn
            FROM user_words
        )
        DELETE FROM user_words
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    op.drop_index("uq_user_word_category", table_name="user_words")
    op.create_index(
        "uq_user_word", "user_words", ["user_id", "word_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_user_word", table_name="user_words")
    op.execute(
        "CREATE UNIQUE INDEX uq_user_word_category "
        "ON user_words (user_id, word_id, COALESCE(category_id, 0))"
    )
