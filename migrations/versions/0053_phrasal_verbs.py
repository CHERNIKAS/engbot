"""Give packs an explicit order, and stop burying the phrasal verbs.

Two problems with one cause.

`give up`, `find out`, `look forward to` — all twenty phrasal verbs are
multi-word, so the corpus ranks none of them, and the word queue sorts unranked
entries last. They sat behind two thousand ranked words, exactly as the
phrasebook did before migration 0052. They are learned whole, like a phrase,
so they belong in the same stream.

But that stream reads its order from `packs.id`, and the phrasal-verbs pack was
created long before the phrasebook — id 7 against 21 and up. Joining the stream
would have put `look forward to` ahead of «How are you?», which is worse than
being buried.

Insertion order was never the teaching order; it only looked like it because
the packs happened to be written in a sensible sequence. `position` says it
outright, so a pack added later can be placed anywhere, and the themes get
their sequence from `app.domain.themes` rather than from the order a migration
ran.

Revision ID: 0053
Revises: 0052
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.domain.themes import THEMES

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

# Greetings first, then the situations a traveller meets in order. Phrasal
# verbs come after all of them: they are the same kind of item, but a learner
# needs to say hello before they need «look forward to».
PHRASE_ORDER = (
    "phrases_small_talk",
    "phrases_travel",
    "phrases_restaurant",
    "phrases_hotel",
    "phrases_doctor",
    "phrases_shopping",
    "phrases_directions",
    "phrases_phone",
    "phrasal_verbs_core",
)


def upgrade() -> None:
    op.add_column(
        "packs",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    bind = op.get_bind()

    for i, slug in enumerate(PHRASE_ORDER):
        bind.execute(
            sa.text("UPDATE packs SET position = :pos WHERE slug = :slug"),
            {"pos": i, "slug": slug},
        )
    for i, theme in enumerate(THEMES):
        bind.execute(
            sa.text("UPDATE packs SET position = :pos WHERE slug = :slug"),
            {"pos": i, "slug": f"topic_{theme.slug}"},
        )

    # Phrasal verbs join the phrase stream: whole lexical units with no corpus
    # rank, which is precisely what that stream exists to carry.
    bind.execute(
        sa.text(
            "UPDATE words SET is_phrase = true WHERE track = 'en' AND id IN ("
            "  SELECT pw.word_id FROM pack_words pw"
            "  JOIN packs p ON p.id = pw.pack_id"
            "  WHERE p.slug = 'phrasal_verbs_core'"
            ")"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_phrase = false WHERE track = 'en' AND id IN ("
            "  SELECT pw.word_id FROM pack_words pw"
            "  JOIN packs p ON p.id = pw.pack_id"
            "  WHERE p.slug = 'phrasal_verbs_core'"
            ")"
        )
    )
    op.drop_column("packs", "position")
