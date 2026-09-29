"""Fill in the second thousand of the corpus list, and clean up four old entries.

507 words from NGSL ranks 1001–2000 join the catalogue, taking that band from
495 of 1000 to 1002 — the material of a second year, which until now simply ran
out. They arrive with the same pipeline and the same level scale as the first
thousand, so the catalogue stays one calibration rather than two.

Three were left out on purpose: four function words the stoplist owns
(`unless`, `onto`, `ought`, `unlike`), and `gray`, which is a spelling of
`grey` rather than a second word — teaching both would make «серый → ?»
unanswerable.

Seventeen generated translations collided with one another or with a word
already in the catalogue («серый» for both greys, «часто» for `often` and
`frequently`). Each was narrowed to what it actually means. The forward card
would have survived — `quiz_distractors` drops a distractor sharing a meaning
with the answer — but the reverse card asks for the English from the Russian,
and there two identical translations have no right answer.

The rest are four small fixes that share one theme — a word in the queue that
teaches something other than itself.

`thought` sits at NGSL rank 47, which puts it in the first fifty words a
beginner meets, and its translation read «мысль / думал (прош. от think)».
That is two lessons in one card: the noun, which earns the rank on its own, and
a past tense the learner has not reached. It keeps its place and loses the
second half — marking it an inflection would drop the noun out of the first
fifty, which is not what the rank says.

`saw` and `found` go the other way. Neither has a frequent meaning of its own
at the rank it holds — «пила» and «основывать» are not why these appear at 50
and 2807 — so they are forms, and the irregular-verb topic drills them as a
table. This is the criterion, and it is worth stating because the obvious one
is wrong: a word is a form when it has no frequent meaning of its own, not when
it happens to be spelled like one. Judged by spelling, `left`, `works` and
`means` would all be deleted from the first thousand.

`fuck` and `ah` are withheld from teaching. Not deleted: the row carries
whatever progress anyone already has, and a flag is visible and reversible
where a delete is neither.

And nine words already in the catalogue get the `ngsl_rank` they were missing —
`fair`, `email`, `guest` and the rest are in the second thousand of the corpus
list but arrived here by another route. Generating them again would have made a
duplicate with a different translation.

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

# (writing, ngsl_rank) — present in the catalogue, missing the corpus rank.
MISSING_RANK = [
    ("fair", 1080),
    ("email", 1169),
    ("guest", 1430),
    ("channel", 1532),
    ("wild", 1591),
    ("plate", 1705),
    ("online", 1794),
    ("appointment", 1839),
    ("bike", 1979),
]

BAND2_FILE = (
    Path(__file__).resolve().parents[2]
    / "app" / "infrastructure" / "data" / "ngsl_band2.json"
)


# ---- ranks held by the wrong word ----------------------------------------- #
#
# A derived form was given its headword's corpus rank: `thought` carries 47,
# which belongs to `think`; `known` carries 41, which belongs to `know`. Measured
# 2026-09-30 across the whole catalogue: 59 ranks were occupied more than once,
# 27 of them by teachable words, and this migration's own new words would have
# added six more — `camp` beside `camping`, `freeze` beside `freezing`.
#
# The learner sees the consequence: two spellings of one idea arriving days
# apart, which is the complaint v2 started from.
#
# The rank goes to the headword — the lemma NGSL actually lists — and the
# derived word keeps its place in the catalogue with `ngsl_rank` cleared. It is
# not marked an inflection: `tired`, `interesting`, `building` all have meanings
# of their own, and the criterion is "no frequent meaning of its own", not
# "looks like a form of something".
#
# Without a corpus rank they fall through to `freq_rank`, which is exactly what
# that column is for, so the two with none get one.
# (derived, rank it wrongly held, freq_rank to set — None keeps what is there)
STOLEN_RANKS: list[tuple[str, int, int | None]] = [
    ("known", 41, 2),  # → know
    ("thought", 47, 1),  # → think
    ("given", 77, 1),  # → give
    ("needed", 90, 1),  # → need
    ("children", 102, 1),  # → child
    ("meeting", 135, 1),  # → meet
    ("interesting", 142, None),  # → interest
    ("later", 147, 1),  # → late
    ("running", 192, 2),  # → run
    ("opening", 214, 2),  # → open
    ("building", 221, 1),  # → build
    ("holding", 222, 1),  # → hold
    ("lost", 305, 1),  # → lose
    ("broken", 368, 2),  # → break
    ("killed", 533, 2),  # → kill
    ("feet", 576, 2),  # → foot
    ("surprised", 634, 2),  # → surprise
    ("painting", 672, 2),  # → paint
    ("fishing", 828, 3),  # → fish
    ("dancing", 959, 2),  # → dance
    ("excited", 1142, 2),  # → excite
    ("swimming", 1391, 2),  # → swim
    ("shoes", 1476, 1),  # → shoe
    ("amazing", 1524, None),  # → amaze
    ("bored", 1690, 2),  # → bore
    ("confused", 1919, 2),  # → confuse
    # Added by this migration's own new words, same problem:
    ("camping", 1165, 3),
    ("tired", 1331, 1),
    ("cycling", 1394, 3),
    ("complicated", 1851, 3),
    ("disappointed", 1853, 2),
    ("freezing", 1856, 2),
]

# `children` and `feet` have no meaning of their own — they are the plural and
# nothing else, and the «Множественное число» topic drills them as a table. A
# word whose entire content is another word's plural is a form by the criterion,
# so they leave the vocabulary rotation the same way `drove` did. `shoes` stays
# a word: «обувь» is how it is actually used, not merely the plural of a shoe.
INFLECTIONS = ["saw", "found", "children", "feet"]
EXCLUDED = ["fuck", "ah"]

THOUGHT_NEW = "мысль"
THOUGHT_OLD = "мысль / думал (прош. от think)"


def upgrade() -> None:
    op.add_column(
        "words",
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    bind = op.get_bind()

    for writing, rank in MISSING_RANK:
        bind.execute(
            sa.text(
                "UPDATE words SET ngsl_rank = :rank"
                " WHERE track = 'en' AND lower(writing) = :w AND ngsl_rank IS NULL"
            ),
            {"rank": rank, "w": writing},
        )


    for derived, rank, freq in STOLEN_RANKS:
        bind.execute(
            sa.text(
                "UPDATE words SET ngsl_rank = NULL"
                " WHERE track = 'en' AND lower(writing) = :w AND ngsl_rank = :rank"
            ),
            {"w": derived, "rank": rank},
        )
        if freq is not None:
            bind.execute(
                sa.text(
                    "UPDATE words SET freq_rank = :freq"
                    " WHERE track = 'en' AND lower(writing) = :w AND freq_rank IS NULL"
                ),
                {"freq": freq, "w": derived},
            )

    bind.execute(
        sa.text(
            "UPDATE words SET is_inflection = true"
            " WHERE track = 'en' AND lower(writing) = ANY(:ws)"
        ),
        {"ws": INFLECTIONS},
    )
    bind.execute(
        sa.text(
            "UPDATE words SET is_excluded = true WHERE track = 'en' AND lower(writing) = ANY(:ws)"
        ),
        {"ws": EXCLUDED},
    )
    bind.execute(
        sa.text(
            "UPDATE words SET translation = :new"
            " WHERE track = 'en' AND lower(writing) = 'thought'"
        ),
        {"new": THOUGHT_NEW},
    )

    # Insert by writing, skipping anything already there: the band was measured
    # against this catalogue, but a re-run must not double a word.
    rows = json.loads(BAND2_FILE.read_text(encoding="utf-8"))
    for row in rows:
        bind.execute(
            sa.text(
                "INSERT INTO words (track, writing, normalized_word, translation, level,"
                " ngsl_rank, polysemous, is_function_word, is_inflection, is_phrase, is_excluded)"
                " SELECT 'en', :w, :norm, :tr, :lvl, :rank, :poly, false, false, false, false"
                " WHERE NOT EXISTS ("
                "   SELECT 1 FROM words WHERE track = 'en' AND lower(writing) = :norm)"
            ),
            {
                "w": row["w"],
                "norm": row["w"].lower(),
                "tr": row["translation"],
                "lvl": row["level"],
                "rank": row["ngsl_rank"],
                "poly": row["polysemous"],
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    for derived, rank, _freq in STOLEN_RANKS:
        bind.execute(
            sa.text(
                "UPDATE words SET ngsl_rank = :rank"
                " WHERE track = 'en' AND lower(writing) = :w AND ngsl_rank IS NULL"
            ),
            {"w": derived, "rank": rank},
        )
    rows = json.loads(BAND2_FILE.read_text(encoding="utf-8"))
    # Only the rows this migration created: a word someone has since started
    # learning keeps its progress, and deleting it would take that with it.
    bind.execute(
        sa.text(
            "DELETE FROM words WHERE track = 'en' AND lower(writing) = ANY(:ws)"
            " AND id NOT IN (SELECT word_id FROM user_words)"
        ),
        {"ws": [r["w"].lower() for r in rows]},
    )
    bind.execute(
        sa.text(
            "UPDATE words SET translation = :old"
            " WHERE track = 'en' AND lower(writing) = 'thought'"
        ),
        {"old": THOUGHT_OLD},
    )
    bind.execute(
        sa.text(
            "UPDATE words SET is_inflection = false"
            " WHERE track = 'en' AND lower(writing) = ANY(:ws)"
        ),
        {"ws": INFLECTIONS},
    )
    for writing, _rank in MISSING_RANK:
        bind.execute(
            sa.text("UPDATE words SET ngsl_rank = NULL WHERE track = 'en' AND lower(writing) = :w"),
            {"w": writing},
        )
    op.drop_column("words", "is_excluded")
