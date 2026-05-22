"""words.part_of_speech + backfill words.level from level packs

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-22

Adds the metadata quiz distractors need to be sensible (same part of speech /
level as the answer instead of random):
- words.part_of_speech ('verb' | 'noun' | 'adj'), backfilled deterministically
  from POS-homogeneous packs (irregular/phrasal verbs -> verb, colors -> adj)
  plus a Russian-suffix heuristic on the translation (see app.domain.pos).
  Left NULL when it can't be inferred confidently.
- words.level (A1/A2/B1/B2), backfilled from the level_* packs the word sits in.

No external data, no fabrication.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.domain.pos import infer_part_of_speech

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_LEVEL_PACKS = [
    ("level_a1", "A1"),
    ("level_a2", "A2"),
    ("level_b1", "B1"),
    ("level_b2", "B2"),
]
_VERB_PACKS = ("irregular_verbs_core", "phrasal_verbs_core")
_ADJ_PACKS = ("theme_colors",)


def _ids_in_packs(conn, slugs: tuple[str, ...]) -> set[int]:
    rows = conn.execute(
        sa.text(
            "SELECT pw.word_id FROM pack_words pw "
            "JOIN packs p ON p.id = pw.pack_id WHERE p.slug IN :slugs"
        ).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": list(slugs)},
    ).all()
    return {r[0] for r in rows}


def _bulk_set_pos(conn, ids: list[int], pos: str) -> None:
    if not ids:
        return
    conn.execute(
        sa.text(
            "UPDATE words SET part_of_speech = :pos WHERE id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)),
        {"pos": pos, "ids": ids},
    )


def upgrade() -> None:
    op.add_column("words", sa.Column("part_of_speech", sa.String(length=16), nullable=True))
    conn = op.get_bind()

    # --- level: copy from the level_* pack each word belongs to (first wins) ---
    for slug, level in _LEVEL_PACKS:
        conn.execute(
            sa.text(
                "UPDATE words SET level = :lvl WHERE level IS NULL AND id IN ("
                "  SELECT pw.word_id FROM pack_words pw "
                "  JOIN packs p ON p.id = pw.pack_id WHERE p.slug = :slug)"
            ),
            {"lvl": level, "slug": slug},
        )

    # --- part of speech: pack overrides first, then the RU-suffix heuristic ---
    verb_ids = _ids_in_packs(conn, _VERB_PACKS)
    adj_ids = _ids_in_packs(conn, _ADJ_PACKS)
    forced = verb_ids | adj_ids

    buckets: dict[str, list[int]] = {"verb": list(verb_ids), "adj": list(adj_ids)}
    rows = conn.execute(
        sa.text("SELECT id, translation FROM words WHERE track = 'en'")
    ).all()
    for wid, translation in rows:
        if wid in forced:
            continue
        pos = infer_part_of_speech(translation)
        if pos:
            buckets.setdefault(pos, []).append(wid)

    for pos, ids in buckets.items():
        _bulk_set_pos(conn, ids, pos)


def downgrade() -> None:
    conn = op.get_bind()
    # words.level was entirely NULL before this migration — restore that for the
    # rows we filled from level packs.
    conn.execute(
        sa.text(
            "UPDATE words SET level = NULL WHERE id IN ("
            "  SELECT pw.word_id FROM pack_words pw "
            "  JOIN packs p ON p.id = pw.pack_id WHERE p.slug IN :slugs)"
        ).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": [slug for slug, _ in _LEVEL_PACKS]},
    )
    op.drop_column("words", "part_of_speech")
