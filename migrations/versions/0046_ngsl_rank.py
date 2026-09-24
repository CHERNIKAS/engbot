"""Give every word a real corpus rank to be ordered by.

`freq_rank` was a 1-to-5 guess from a language model, and five buckets cannot
order two thousand words: prod had `salad`, `Friday` and `cheese` sharing a
bucket with `you`, `not` and `the`. Inside a CEFR level the queue was therefore
arbitrary, which is how an A1 learner was served `giggle`, `frown` and `gaze`
while 687 A1 words sat in `new`, untouched.

`ngsl_rank` replaces the guess with the New General Service List: 2801
headwords from a 273-million-word corpus, ~92% coverage of general English.
Inflections resolve to their headword, so `drove` ranks as `drive` rather than
falling off the list.

NULL means the word is not on the list. That is not "worst" — it covers both
narrow terms (`blockchain`) and everyday nouns the corpus omits (`apple`,
`airport`), which the thematic collections carry instead. Ordering must send
NULLs last rather than treat them as rank zero.

`freq_rank` is left in place: it still describes the ~900 catalogue words that
are off-list, where it is the only signal available.

Attribution: app/infrastructure/data/NOTICE.md

Revision ID: 0046
Revises: 0045
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.domain.ngsl import rank_of

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("words", sa.Column("ngsl_rank", sa.Integer(), nullable=True))
    op.create_index(
        "ix_words_track_ngsl_rank", "words", ["track", "ngsl_rank"], unique=False
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, writing FROM words WHERE track = 'en'")
    ).fetchall()
    ranked = [
        {"wid": wid, "rank": rank}
        for wid, writing in rows
        if (rank := rank_of(writing)) is not None
    ]
    if ranked:
        bind.execute(
            sa.text("UPDATE words SET ngsl_rank = :rank WHERE id = :wid"), ranked
        )


def downgrade() -> None:
    op.drop_index("ix_words_track_ngsl_rank", table_name="words")
    op.drop_column("words", "ngsl_rank")
