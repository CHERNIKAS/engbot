"""Stop teaching a word's past tense as if it were a separate word.

The catalogue carries 90 entries that the New General Service List resolves to
some other headword. Most are harmless duplicates of effort — `drove` costs a
learner the same eight repetitions as `drive` and teaches nothing `drive` does
not — but the cards themselves are worse than useless: «drove — вел машину»
asks someone to memorise a translation of a tense.

Irregular forms are real knowledge, so nothing here is deleted. They move to
where the form *is* the lesson: the irregular-verbs collection drills
drive / drove / driven as a table, and `better` / `best` belong to the
comparatives topic, which already covers them.

What is NOT flagged matters as much as what is. Checking each form against its
own stored translation showed that a rule would have destroyed real vocabulary:

    building  — здание        not "the act of building"
    meeting   — встреча       swimming — плавание, a sport
    tired     — уставший      broken   — сломанный
    children  — дети          saw      — пила, as well as a past tense
    interesting — интересный  shoes    — обувь

So this is an explicit list, not a rule. Every entry is either a past tense or
past participle with no life of its own, a comparative that grammar owns, a
British spelling of a word already present, or slang.

Revision ID: 0051
Revises: 0050
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

# Past tense and participles whose gloss is the tense, not a meaning.
VERB_FORMS = (
    "became", "began", "broke", "brought", "came", "caught", "drove", "fell",
    "felt", "gave", "gone", "got", "gotten", "heard", "hung", "kept", "knew",
    "laid", "meant", "ran", "said", "sat",
)

# The comparatives topic teaches these as a pattern; a card for «лучше» alone
# leaves the learner unable to form any other comparative.
COMPARATIVES = ("better", "best")

# British spellings of entries already in the catalogue. Kept as rows so the
# answer checker can still accept them from a learner who writes them.
SPELLING_VARIANTS = ("behaviour", "colour", "neighbour")

SLANG = ("gonna",)

INFLECTIONS = VERB_FORMS + COMPARATIVES + SPELLING_VARIANTS + SLANG


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column("is_inflection", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE words SET is_inflection = true "
            "WHERE track = 'en' AND lower(writing) = ANY(:names)"
        ),
        {"names": list(INFLECTIONS)},
    )


def downgrade() -> None:
    op.drop_column("words", "is_inflection")
