"""Move the narrow packs out of the themes so they stop jumping the queue.

Five packs predate the theme rebuild and share its category: crypto, IT,
business, a travel phrasebook and a basic-verbs list. Migration 0050 replaced
the hand-made themes but left these, and they kept `position = 0` — which sorts
them ahead of every theme in the new sequence. The top-up walks that order, so
the first words a beginner would have been given are crypto vocabulary.

They are not deleted: narrow vocabulary is worth having for whoever wants it,
and that was the decision. They move to a category of their own, where nothing
adds them automatically and the learner picks them up deliberately.

`travel_essentials` is a phrasebook rather than a word list, but it sits with
the others for the same reason — it duplicates the `phrases_travel` pack the
phrase stream already teaches in order, and having both means the airport
arrives twice.

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

NARROW = (
    "crypto_basics",
    "it_starter",
    "business_basic",
    "travel_essentials",
    "basic_english_verbs",
)

NARROW_CATEGORY = "Узкие темы"
OLD_CATEGORY = "Темы"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE packs SET category = :cat WHERE slug = ANY(:slugs)"),
        {"cat": NARROW_CATEGORY, "slugs": list(NARROW)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE packs SET category = :cat WHERE slug = ANY(:slugs)"),
        {"cat": OLD_CATEGORY, "slugs": list(NARROW)},
    )
