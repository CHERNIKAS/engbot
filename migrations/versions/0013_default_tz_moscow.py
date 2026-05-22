"""default timezone Europe/Moscow + migrate stale UTC users

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-22

The push window and "today/streak" are evaluated in the user's timezone,
which defaulted to UTC. For a RU-speaking audience that's wrong by ~3h:
a 10:00–22:00 window ran 13:00–01:00 Moscow time (late-night spam, no
morning pushes). Switch the default to Europe/Moscow and move users still
sitting on the old UTC default to Moscow. Anyone can re-pick their zone in
Settings → 🕐 Часовой пояс.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "timezone", server_default="Europe/Moscow")
    # Users still on the old default never had a timezone picker; nudge them to
    # Moscow so the push window is sane out of the box.
    op.execute("UPDATE users SET timezone = 'Europe/Moscow' WHERE timezone = 'UTC'")


def downgrade() -> None:
    # Revert only the schema default. Leave existing rows untouched — we can't
    # tell which were originally UTC vs deliberately set, and clobbering a
    # user's chosen zone on rollback would be worse than a stale default.
    op.alter_column("users", "timezone", server_default="UTC")
