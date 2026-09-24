"""Widen the function-word flag to everything grammar already owns.

Migration 0040 flagged twenty entries — articles and negated auxiliaries. That
covered the cards that were visibly broken, not the category. Measuring the
catalogue against the New General Service List showed the rest of it: 69% of
the hundred most frequent English words are function words, so a frequency-
ordered intake hands a beginner `of`, `to`, `in`, `for`, `on`, `with`, `as`,
`at` as their first fourteen cards before reaching a single content word.

With the wider list those same first cards become say, go, know, get, like,
think, make, time, see — which is what the learner came for. The cost is 128 of
2809 NGSL entries, every one of which is taught by an existing grammar topic
(prepositions, modals, much/many/some/any, question order) where it gets a rule
and context instead of four buttons.

Numbers are deliberately absent from the list: they are exact pairs that must
be memorised, and the flag is a hard filter in every picker, so flagging them
would leave a numbers topic with nothing to serve.

Rows are flagged, never deleted — users own progress on them, and a flag is
reversible where a delete is not.

Revision ID: 0045
Revises: 0044
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.domain.function_words import FUNCTION_WORDS

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

# What 0040 set, so downgrade restores exactly that state rather than clearing
# the flag wholesale and silently undoing the earlier migration too.
_0040_WORDS = (
    "a", "an", "the", "it's",
    "aren't", "can't", "couldn't", "didn't", "doesn't", "don't",
    "hadn't", "hasn't", "haven't", "isn't", "mustn't", "shouldn't",
    "wasn't", "weren't", "won't", "wouldn't",
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_function_word = true "
            "WHERE track = 'en' AND lower(writing) = ANY(:names)"
        ),
        {"names": sorted(FUNCTION_WORDS)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_function_word = (lower(writing) = ANY(:kept)) "
            "WHERE track = 'en' AND lower(writing) = ANY(:names)"
        ),
        {"names": sorted(FUNCTION_WORDS), "kept": list(_0040_WORDS)},
    )
