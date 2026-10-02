"""Give the 195 catalogue words outside NGSL a rank of their own.

`ngsl_rank` orders everything the corpus list covers, and `freq_rank` is what
decides the order below it. Until now these 195 had neither, so they sorted
last by `nulls_last` — not because they were rare, but because nobody had said
anything about them. «january», «glasses» and «eighteen» sat behind «abolish».

The scale already in use is 1 to 4, lower meaning more common. What it is not
is a measurement: unlike `ngsl_rank`, which comes from a published corpus
count, these are a judgement about how early a learner meets the word. They are
assigned in four groups, and the grouping is the honest part of the claim:

  1 — numbers, months, nationalities, everyday objects and states
  2 — common beyond the basics: jobs, feelings, ordinary abstractions
  3 — academic and formal register, the vocabulary of written argument
  4 — formal to the point of rarity

Nothing here is inferred from frequency data we hold, and the migration says so
rather than letting a number look like a count.

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

# (writing, freq_rank)
RANKS: tuple[tuple[str, int], ...] = (
    ("abolish", 3),
    ("absorb", 2),
    ("abundant", 3),
    ("accumulate", 3),
    ("accustomed", 3),
    ("acute", 3),
    ("adverse", 3),
    ("aesthetic", 3),
    ("allocate", 3),
    ("amazing", 1),
    ("ambiguous", 3),
    ("ambition", 2),
    ("analogy", 3),
    ("annoy", 2),
    ("april", 1),
    ("arbitrary", 3),
    ("articulate", 3),
    ("asleep", 1),
    ("assert", 3),
    ("attain", 3),
    ("august", 1),
    ("authentic", 3),
    ("autonomy", 3),
    ("autumn", 1),
    ("bake", 1),
    ("birthday", 1),
    ("bitter", 1),
    ("boil", 1),
    ("bolster", 4),
    ("brave", 1),
    ("cashier", 2),
    ("catalyst", 3),
    ("cave", 1),
    ("cease", 3),
    ("check-in", 1),
    ("check-out", 1),
    ("chew", 1),
    ("chinese", 1),
    ("cinema", 1),
    ("clever", 1),
    ("click", 1),
    ("coherent", 3),
    ("coin", 1),
    ("coincide", 3),
    ("collaborate", 3),
    ("commence", 4),
    ("compel", 3),
    ("compile", 3),
    ("complement", 3),
    ("conceive", 3),
    ("concise", 4),
    ("condemn", 3),
    ("confine", 3),
    ("conform", 3),
    ("consensus", 3),
    ("consolidate", 3),
    ("constrain", 3),
    ("contemplate", 3),
    ("contradict", 3),
    ("controversy", 3),
    ("convey", 3),
    ("correlate", 3),
    ("credible", 3),
    ("culminate", 4),
    ("december", 1),
    ("deduce", 3),
    ("deem", 3),
    ("deliberate", 2),
    ("denote", 3),
    ("dense", 2),
    ("depart", 2),
    ("depict", 3),
    ("deprive", 3),
    ("deteriorate", 3),
    ("detrimental", 3),
    ("diminish", 3),
    ("diverse", 2),
    ("domain", 3),
    ("dynamic", 2),
    ("eight", 1),
    ("eighteen", 1),
    ("eighty", 1),
    ("eleven", 1),
    ("endure", 3),
    ("english", 1),
    ("evident", 2),
    ("exaggerate", 2),
    ("exclusive", 2),
    ("explicit", 2),
    ("exploit", 3),
    ("facilitate", 3),
    ("feasible", 3),
    ("february", 1),
    ("fifteen", 1),
    ("fifty", 1),
    ("finite", 3),
    ("forgive", 1),
    ("fork", 1),
    ("forty", 1),
    ("fourteen", 1),
    ("french", 1),
    ("fry", 1),
    ("generous", 1),
    ("german", 1),
    ("glasses", 1),
    ("hairdresser", 2),
    ("handsome", 1),
    ("hardworking", 2),
    ("honesty", 2),
    ("hungry", 1),
    ("impact", 2),
    ("implicit", 3),
    ("inevitable", 2),
    ("inherent", 3),
    ("insect", 1),
    ("interesting", 1),
    ("intervene", 3),
    ("intrinsic", 3),
    ("italian", 1),
    ("january", 1),
    ("japanese", 1),
    ("july", 1),
    ("june", 1),
    ("knit", 2),
    ("leaf", 1),
    ("legitimate", 2),
    ("living room", 1),
    ("manipulate", 2),
    ("march", 1),
    ("may", 1),
    ("menu", 1),
    ("minimal", 2),
    ("nationality", 2),
    ("neutral", 2),
    ("nineteen", 1),
    ("ninety", 1),
    ("norm", 2),
    ("november", 1),
    ("obey", 2),
    ("obstacle", 2),
    ("october", 1),
    ("offline", 2),
    ("ongoing", 2),
    ("optimal", 3),
    ("parcel", 2),
    ("pasta", 2),
    ("patience", 1),
    ("pet", 1),
    ("plausible", 3),
    ("polite", 1),
    ("preliminary", 3),
    ("prevail", 3),
    ("profound", 3),
    ("prominent", 2),
    ("rainy", 1),
    ("rational", 2),
    ("receipt", 1),
    ("reception", 2),
    ("reinforce", 2),
    ("rigid", 2),
    ("robust", 2),
    ("rude", 1),
    ("russian", 1),
    ("salty", 1),
    ("scared", 1),
    ("scenario", 2),
    ("seize", 2),
    ("september", 1),
    ("seventeen", 1),
    ("seventy", 1),
    ("sew", 2),
    ("shy", 1),
    ("sixteen", 1),
    ("sixty", 1),
    ("slim", 1),
    ("sneeze", 2),
    ("soda", 1),
    ("sour", 1),
    ("spanish", 1),
    ("spicy", 1),
    ("spider", 1),
    ("subtle", 2),
    ("supermarket", 1),
    ("t-shirt", 1),
    ("thirsty", 1),
    ("thirteen", 1),
    ("thirty", 1),
    ("trait", 2),
    ("umbrella", 1),
    ("undermine", 2),
    ("viable", 3),
    ("vivid", 2),
    ("whistle", 2),
    ("wifi", 1),
    ("zero", 1),)


def upgrade() -> None:
    bind = op.get_bind()
    for writing, rank in RANKS:
        bind.execute(
            # Two binds, not one: `:norm` is compared against `lower(writing)`
            # and `:rank` is written to an integer column. Reusing a single bind
            # for a comparison and a value is what made 0061 fail to deduce a
            # type — the same mistake 0047 and 0048 made before it.
            sa.text(
                "UPDATE words SET freq_rank = :rank"
                " WHERE track = 'en' AND lower(writing) = :norm AND freq_rank IS NULL"
            ),
            {"rank": rank, "norm": writing},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for writing, rank in RANKS:
        # Only clears what this migration set: a rank given since by any other
        # route is not ours to remove.
        bind.execute(
            sa.text(
                "UPDATE words SET freq_rank = NULL"
                " WHERE track = 'en' AND lower(writing) = :norm AND freq_rank = :rank"
            ),
            {"rank": rank, "norm": writing},
        )
