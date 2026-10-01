"""Mark who owns each pack, so the admin and the migrations stop overwriting each other.

Packs are edited by migrations today, and the admin screens added alongside this
would edit the same rows. Whichever ran last would win, silently: a hand fix
would vanish on the next deploy, or a shipped correction would be reverted by a
stale hand edit.

`origin` splits ownership. Migrations touch `migration` rows only. The admin may
edit anything, but editing a `migration` pack moves it to `admin` — after that
the migrations leave it alone.

That makes one failure mode possible, and it is the dangerous one: a migration
that ships a fix for a pack somebody has since edited by hand will skip it and
report success. So skipping is never silent — `report_skipped()` prints what it
passed over, during the upgrade, where a deploy log will show it. The point is
that the divergence is visible the moment it happens rather than discovered a
month later.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

ORIGIN_MIGRATION = "migration"
ORIGIN_ADMIN = "admin"


def upgrade() -> None:
    op.add_column(
        "packs",
        sa.Column(
            "origin",
            sa.String(16),
            nullable=False,
            server_default=ORIGIN_MIGRATION,
        ),
    )
    # Everything that exists now came from a migration, by definition: there was
    # no other way to create a pack until this revision.
    op.execute(f"UPDATE packs SET origin = '{ORIGIN_MIGRATION}'")


def downgrade() -> None:
    op.drop_column("packs", "origin")
