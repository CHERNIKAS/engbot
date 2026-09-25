"""Give every grammar topic its construction phrases.

Present Simple got its hundred in 0055 and the rest got nothing, so the
constructor could teach exactly one topic. The moment a learner passed it,
grammar had nothing left to serve.

The phrases live in `app/infrastructure/data/constructor/<slug>.json` rather
than inside this file. Twenty-nine topics at a hundred phrases each is about
twenty thousand lines of literals — unreviewable in a diff, and the same data
has to be read by the integrity test anyway. Keeping one copy means the test
checks what actually gets inserted.

Every phrase was verified before insertion: the slots concatenate into exactly
`en`, each slot offers its own answer, and no Russian sentence repeats within a
topic. The first of those is the one that matters — when the tiles assemble
into something the typing checker rejects, the learner is told they are wrong
for following the only path the card offered.

Topics whose file is missing are skipped rather than failing the migration:
content arrives topic by topic, and a half-filled catalogue is the normal
intermediate state. A topic with no phrases is simply not offered — see
`ConstructorRepository.active_topic`.

Revision ID: 0060
Revises: 0059
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

DATA_DIR = Path(__file__).resolve().parents[2] / "app" / "infrastructure" / "data" / "constructor"


def upgrade() -> None:
    bind = op.get_bind()
    if not DATA_DIR.exists():
        return

    for path in sorted(DATA_DIR.glob("*.json")):
        slug = path.stem
        topic_id = bind.execute(
            sa.text("SELECT id FROM grammar_topics WHERE slug = :slug"), {"slug": slug}
        ).scalar()
        if topic_id is None:
            continue
        # Re-running must not double the set: a topic that already has phrases
        # keeps the ones it has.
        existing = bind.execute(
            sa.text("SELECT count(*) FROM grammar_phrases WHERE topic_id = :tid"),
            {"tid": topic_id},
        ).scalar_one()
        if existing:
            continue

        rows = json.loads(path.read_text(encoding="utf-8"))
        if not rows:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO grammar_phrases (topic_id, ru, en, alternatives, slots, position)"
                " VALUES (:topic_id, :ru, :en, CAST(:alts AS jsonb), CAST(:slots AS jsonb), :pos)"
            ),
            [
                {
                    "topic_id": topic_id,
                    "ru": row["ru"],
                    "en": row["en"],
                    "alts": json.dumps(row.get("alternatives") or [], ensure_ascii=False),
                    "slots": json.dumps(row["slots"], ensure_ascii=False),
                    "pos": i,
                }
                for i, row in enumerate(rows)
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not DATA_DIR.exists():
        return
    slugs = [p.stem for p in DATA_DIR.glob("*.json")]
    if not slugs:
        return
    bind.execute(
        sa.text(
            "DELETE FROM grammar_phrases WHERE topic_id IN"
            " (SELECT id FROM grammar_topics WHERE slug = ANY(:slugs))"
        ),
        {"slugs": slugs},
    )
