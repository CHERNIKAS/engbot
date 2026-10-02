"""Move @tannache's push window from code into her settings.

Her window was pinned in code (`PUSH_WINDOW_OVERRIDES`, 14:00–21:00), which
silently beat whatever she chose in «Настройки»: her stored setting read
14:00–01:00 and did nothing. The owner kept 14–21 (2026-10-03); it now lives
where every other learner's window does, and the override table is gone, so
the setting she sees is the one that applies.

Revision ID: 0067
Revises: 0066
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

TELEGRAM_ID = 553133186
OLD = {"push_ws": 14, "push_we": 1}  # what her settings held before this


def _set(ws: int, we: int) -> None:
    op.get_bind().execute(
        sa.text(
            "update user_tracks set settings = coalesce(settings, '{}'::jsonb)"
            " || jsonb_build_object('push_ws', cast(:ws as int), 'push_we', cast(:we as int))"
            " where track = 'en' and user_id = (select id from users where telegram_id = cast(:tg as bigint))"
        ),
        {"ws": ws, "we": we, "tg": TELEGRAM_ID},
    )


def upgrade() -> None:
    _set(14, 21)


def downgrade() -> None:
    _set(OLD["push_ws"], OLD["push_we"])
