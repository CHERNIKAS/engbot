"""grammar pack 2: articles + prepositions

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-23

Adds two more grammar topics (choose-the-form, choice-only) into the existing
grammar tables, after the tense topics. Same delivery (course/push). Idempotent
by slug; downgrade removes the two topics (cascades to items + user progress).
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


GRAMMAR: list[dict] = [
    {
        "slug": "articles_basic",
        "title": "Артикли (a / an / the)",
        "level": "A1",
        "position": 4,
        "rule": (
            "🔤 <b>Артикли</b>:\n"
            "<b>a/an</b> — неопределённый, один из многих (a cat, an apple; an — перед гласным звуком).\n"
            "<b>the</b> — определённый, конкретный/известный (the sun, the book on the table).\n"
            "<b>—</b> (без артикля) — с множественным и неисчисляемым в общем смысле (I love music)."
        ),
        "items": [
            ("I saw ___ cat in the garden.", "a", ["an", "the", "—"]),
            ("She is ___ honest person.", "an", ["a", "the", "—"]),
            ("Can you pass me ___ salt?", "the", ["a", "an", "—"]),
            ("I really love ___ music.", "—", ["a", "an", "the"]),
            ("He bought ___ umbrella.", "an", ["a", "the", "—"]),
            ("___ sun is very bright today.", "The", ["A", "An", "—"]),
            ("We had ___ eggs for breakfast.", "—", ["a", "an", "the"]),
            ("There is ___ apple on the table.", "an", ["a", "the", "—"]),
            ("She plays ___ piano very well.", "the", ["a", "an", "—"]),
            ("He works as ___ engineer.", "an", ["a", "the", "—"]),
            ("Cats are ___ wonderful animals.", "—", ["a", "an", "the"]),
            ("Open ___ door, please.", "the", ["a", "an", "—"]),
        ],
    },
    {
        "slug": "prepositions_basic",
        "title": "Предлоги (in / on / at / to)",
        "level": "A1",
        "position": 5,
        "rule": (
            "📍 <b>Предлоги места и времени</b>:\n"
            "<b>at</b> — точка/точное время (at the bus stop, at 7 o'clock).\n"
            "<b>in</b> — внутри, месяцы/годы (in the box, in May, in 1990).\n"
            "<b>on</b> — на поверхности, дни (on the table, on Monday).\n"
            "<b>to</b> — направление (go to school)."
        ),
        "items": [
            ("I get up ___ 7 o'clock.", "at", ["in", "on", "to"]),
            ("We met ___ Monday.", "on", ["in", "at", "to"]),
            ("She was born ___ 1990.", "in", ["on", "at", "to"]),
            ("The book is ___ the table.", "on", ["in", "at", "to"]),
            ("He lives ___ London.", "in", ["on", "at", "to"]),
            ("I'm going ___ the cinema.", "to", ["in", "on", "at"]),
            ("They arrive ___ the morning.", "in", ["on", "at", "to"]),
            ("Meet me ___ the bus stop.", "at", ["in", "on", "to"]),
            ("There's a picture ___ the wall.", "on", ["in", "at", "to"]),
            ("We travelled ___ Paris by train.", "to", ["in", "on", "at"]),
            ("The cat is hiding ___ the box.", "in", ["on", "at", "to"]),
            ("I'll see you ___ Friday.", "on", ["in", "at", "to"]),
            ("She often works ___ night.", "at", ["in", "on", "to"]),
            ("The keys are ___ my pocket.", "in", ["on", "at", "to"]),
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
