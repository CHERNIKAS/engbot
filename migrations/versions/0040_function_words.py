"""Mark function words so they stop being taught as vocabulary.

Articles and auxiliary contractions cannot work as a "pick the translation"
card. `a` and `an` have no translation to pick at all, and for the negated
auxiliaries every honest distractor differs from the answer only by tense or
number — «не сделал» against «не делает», «не был» against «не были». That is a
grammar question wearing a vocabulary card's clothes: a learner who knows the
word perfectly still picks at random, and the miss costs them score.

Grammar has its own delivery in this bot, with rules and gap-fill exercises.
These belong there, not in the word rotation.

Rows are kept rather than deleted: users own progress on them, and a flag is
reversible where a delete is not.

Revision ID: 0040
Revises: 0039
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

# Matched on `writing`, lower-cased. Kept explicit rather than pattern-matched:
# a regex for "ends in n't" would also catch any future contraction someone
# adds deliberately, and this list is short enough to read.
FUNCTION_WORDS: tuple[str, ...] = (
    "a",
    "an",
    "the",
    "it's",
    "aren't",
    "can't",
    "couldn't",
    "didn't",
    "doesn't",
    "don't",
    "hadn't",
    "hasn't",
    "haven't",
    "isn't",
    "mustn't",
    "shouldn't",
    "wasn't",
    "weren't",
    "won't",
    "wouldn't",
)


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column(
            "is_function_word", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_function_word = true "
            "WHERE track = 'en' AND lower(writing) = ANY(:names)"
        ),
        {"names": list(FUNCTION_WORDS)},
    )


def downgrade() -> None:
    op.drop_column("words", "is_function_word")
