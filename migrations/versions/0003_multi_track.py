"""multi-track foundation: rename english_word, add track + JA fields, user_tracks table

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-03

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- words ---
    op.drop_index("ix_words_normalized_word", table_name="words")
    op.alter_column("words", "english_word", new_column_name="writing")
    op.add_column("words", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.add_column("words", sa.Column("kana", sa.String(128), nullable=True))
    op.add_column("words", sa.Column("romaji", sa.String(128), nullable=True))
    op.add_column("words", sa.Column("script_type", sa.String(16), nullable=True))
    op.add_column("words", sa.Column("level", sa.String(8), nullable=True))
    op.create_index("ix_words_track", "words", ["track"])
    op.create_unique_constraint("uq_words_track_normalized", "words", ["track", "normalized_word"])

    # --- categories ---
    op.add_column("categories", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.create_index("ix_categories_track", "categories", ["track"])
    op.drop_constraint("uq_categories_user_name", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_categories_user_track_name", "categories", ["user_id", "track", "name"]
    )

    # --- user_words ---
    op.add_column("user_words", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.drop_index("ix_user_words_user_next_review", table_name="user_words")
    op.drop_index("ix_user_words_user_status", table_name="user_words")
    op.create_index(
        "ix_user_words_user_track_next_review", "user_words", ["user_id", "track", "next_review_at"]
    )
    op.create_index(
        "ix_user_words_user_track_status", "user_words", ["user_id", "track", "status"]
    )

    # --- packs ---
    op.add_column("packs", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.create_index("ix_packs_track", "packs", ["track"])

    # --- study_sessions ---
    op.add_column("study_sessions", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.create_index("ix_study_sessions_track", "study_sessions", ["track"])

    # --- word_reviews ---
    op.add_column("word_reviews", sa.Column("track", sa.String(8), nullable=False, server_default="en"))
    op.create_index("ix_word_reviews_user_track_date", "word_reviews", ["user_id", "track", "reviewed_at"])

    # --- user_tracks ---
    op.create_table(
        "user_tracks",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track", sa.String(8), primary_key=True),
        sa.Column("daily_goal_words", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("learning_pace", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("daily_goal_words BETWEEN 1 AND 100", name="ck_user_tracks_goal_range"),
    )

    # Backfill user_tracks from existing users.
    op.execute(
        """
        INSERT INTO user_tracks (user_id, track, daily_goal_words, learning_pace, is_active, onboarding_completed, settings)
        SELECT id, 'en', daily_goal_words, learning_pace, true, onboarding_completed, '{}'::jsonb
        FROM users
        """
    )

    # --- users: drop legacy per-track fields ---
    op.drop_constraint("ck_users_daily_goal_range", "users", type_="check")
    op.drop_column("users", "daily_goal_words")
    op.drop_column("users", "learning_pace")


def downgrade() -> None:
    op.add_column("users", sa.Column("learning_pace", sa.String(16), nullable=False, server_default="normal"))
    op.add_column("users", sa.Column("daily_goal_words", sa.Integer(), nullable=False, server_default="10"))
    op.create_check_constraint(
        "ck_users_daily_goal_range", "users", "daily_goal_words BETWEEN 1 AND 100"
    )
    op.execute(
        """
        UPDATE users u
        SET daily_goal_words = COALESCE(ut.daily_goal_words, 10),
            learning_pace = COALESCE(ut.learning_pace, 'normal')
        FROM user_tracks ut
        WHERE ut.user_id = u.id AND ut.track = 'en'
        """
    )

    op.drop_table("user_tracks")

    op.drop_index("ix_word_reviews_user_track_date", table_name="word_reviews")
    op.drop_column("word_reviews", "track")

    op.drop_index("ix_study_sessions_track", table_name="study_sessions")
    op.drop_column("study_sessions", "track")

    op.drop_index("ix_packs_track", table_name="packs")
    op.drop_column("packs", "track")

    op.drop_index("ix_user_words_user_track_status", table_name="user_words")
    op.drop_index("ix_user_words_user_track_next_review", table_name="user_words")
    op.create_index("ix_user_words_user_status", "user_words", ["user_id", "status"])
    op.create_index("ix_user_words_user_next_review", "user_words", ["user_id", "next_review_at"])
    op.drop_column("user_words", "track")

    op.drop_constraint("uq_categories_user_track_name", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_user_name", "categories", ["user_id", "name"])
    op.drop_index("ix_categories_track", table_name="categories")
    op.drop_column("categories", "track")

    op.drop_constraint("uq_words_track_normalized", "words", type_="unique")
    op.drop_index("ix_words_track", table_name="words")
    op.drop_column("words", "level")
    op.drop_column("words", "script_type")
    op.drop_column("words", "romaji")
    op.drop_column("words", "kana")
    op.drop_column("words", "track")
    op.alter_column("words", "writing", new_column_name="english_word")
    op.create_index("ix_words_normalized_word", "words", ["normalized_word"], unique=True)
