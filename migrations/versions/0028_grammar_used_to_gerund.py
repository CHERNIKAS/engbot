"""grammar pack 4: used to + gerund vs infinitive

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-23

Finishes the Phase-1 grammar list: «used to» and gerund/infinitive. Same
choose-the-form pattern; idempotent by slug.
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


GRAMMAR: list[dict] = [
    {
        "slug": "used_to",
        "title": "used to (раньше)",
        "level": "B1",
        "position": 15,
        "rule": (
            "🕰 <b>used to</b> — то, что было регулярно или долго в прошлом, но не сейчас. "
            "<b>used to + базовая форма</b> (I used to smoke). В вопросах/отрицаниях — "
            "<b>did/didn't + use to</b>."
        ),
        "items": [
            ("I ___ play tennis when I was young.", "used to", ["use to", "used", "am used to"]),
            ("She ___ live in Moscow.", "used to", ["use to", "is used to", "used"]),
            ("We ___ have a dog.", "used to", ["use to", "used", "are used to"]),
            ("He didn't ___ like coffee.", "use to", ["used to", "used", "uses to"]),
            ("___ you use to walk to school?", "Did", ["Do", "Were", "Have"]),
            ("They ___ travel a lot before the kids.", "used to", ["use to", "used", "were used to"]),
        ],
    },
    {
        "slug": "gerund_infinitive",
        "title": "Gerund или Infinitive",
        "level": "B1",
        "position": 16,
        "rule": (
            "🔁 После одних глаголов идёт <b>-ing</b> (enjoy, finish, avoid: I enjoy reading), "
            "после других — <b>to + глагол</b> (want, decide, hope: I want to go). "
            "После предлогов — всегда <b>-ing</b>."
        ),
        "items": [
            ("I enjoy ___ books.", "reading", ["to read", "read", "to reading"]),
            ("She wants ___ home.", "to go", ["going", "go", "to going"]),
            ("We decided ___ early.", "to leave", ["leaving", "leave", "to leaving"]),
            ("He finished ___ his homework.", "doing", ["to do", "do", "to doing"]),
            ("They hope ___ the exam.", "to pass", ["passing", "pass", "to passing"]),
            ("Thanks for ___ me.", "helping", ["to help", "help", "to helping"]),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for topic in GRAMMAR:
        if conn.execute(
            sa.text("SELECT id FROM grammar_topics WHERE slug = :s"), {"s": topic["slug"]}
        ).first():
            continue
        tid = conn.execute(
            sa.text(
                "INSERT INTO grammar_topics (slug, track, title, rule, level, position) "
                "VALUES (:slug, 'en', :title, :rule, :level, :position) RETURNING id"
            ),
            {"slug": topic["slug"], "title": topic["title"], "rule": topic["rule"],
             "level": topic["level"], "position": topic["position"]},
        ).scalar()
        for pos, (prompt, correct, distractors) in enumerate(topic["items"]):
            conn.execute(
                sa.text(
                    "INSERT INTO grammar_items (topic_id, prompt, correct, distractors, position) "
                    "VALUES (:t, :p, :c, CAST(:d AS JSONB), :pos)"
                ),
                {"t": tid, "p": prompt, "c": correct, "d": json.dumps(distractors, ensure_ascii=False), "pos": pos},
            )


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [t["slug"] for t in GRAMMAR]
    conn.execute(
        sa.text("DELETE FROM grammar_topics WHERE slug IN :s").bindparams(
            sa.bindparam("s", expanding=True)
        ),
        {"s": slugs},
    )
