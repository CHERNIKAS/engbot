"""Mark phrasebook entries so the frequency ordering stops burying them.

The word queue now sorts by corpus rank. A phrase has none — the New General
Service List ranks single lemmas, so «How much is it?» comes back NULL — and
NULLs sort last. The practical effect is that all 102 phrases moved behind
every ranked word in the catalogue, which is roughly two thousand of them.
They would not have been reached for years.

That is the right call for ordering and the wrong outcome for teaching. A
learner three days in should be able to say «Nice to meet you», and no measure
of corpus frequency will ever put a greeting ahead of `say` and `go`. Phrases
do not belong in that comparison at all: they are a separate kind of thing,
learned whole, and they need their own slot rather than a place in the queue.

So they are flagged here and excluded from the word pickers, and the push
draws them from their own stream instead.

Membership comes from the phrasebook packs rather than from looking for a space
in the writing: `living room`, `post office` and `t-shirt` are ordinary
vocabulary that happens to be spelled with a gap.

Revision ID: 0052
Revises: 0051
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column("is_phrase", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_phrase = true WHERE track = 'en' AND id IN ("
            "  SELECT pw.word_id FROM pack_words pw"
            "  JOIN packs p ON p.id = pw.pack_id"
            "  WHERE p.category = 'Фразы'"
            ")"
        )
    )


def downgrade() -> None:
    op.drop_column("words", "is_phrase")
