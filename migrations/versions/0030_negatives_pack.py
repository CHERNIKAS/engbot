"""content pack: contractions / negatives (a pool of «не …» glosses)

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-23

Function words like haven't/don't/can't translate to «не …», but had no sibling
negations to be quizzed against, so the answer was guessable ("the only one with
«не»"). This pack gives a cluster of negations; the distractor picker now
shape-matches (negation↔negation), so they confuse each other properly.
Idempotent by slug; words upserted by (track, normalized).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

PACK = {
    "slug": "negatives_contractions",
    "title": "🚫 Сокращения и отрицания",
    "description": "Отрицательные формы: haven't, don't, can't, isn't… — все «не …».",
    "category": "Грамматика",
    # (english, translation, example)
    "words": [
        ("haven't", "не имею", "I haven't seen him today."),
        ("hasn't", "не имеет", "She hasn't called yet."),
        ("don't", "не делаю", "I don't like coffee."),
        ("doesn't", "не делает", "He doesn't smoke."),
        ("can't", "не могу", "I can't swim."),
        ("won't", "не буду", "I won't be late."),
        ("isn't", "не является", "This isn't a problem."),
        ("aren't", "не являются", "They aren't ready."),
        ("wasn't", "не был", "I wasn't at home."),
        ("weren't", "не были", "They weren't there."),
        ("didn't", "не делал", "I didn't see it."),
        ("couldn't", "не мог", "I couldn't sleep."),
        ("wouldn't", "не стал бы", "He wouldn't help."),
        ("shouldn't", "не следует", "You shouldn't worry."),
        ("mustn't", "не должен / нельзя", "You mustn't smoke here."),
        ("hadn't", "не имел", "I hadn't met her before."),
    ],
}


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(
        sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": PACK["slug"]}
    ).first():
        return
    word_ids: list[int] = []
    for english, translation, example in PACK["words"]:
        n = english.strip().lower()
        existing = conn.execute(
            sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"), {"n": n}
        ).first()
        if existing:
            # Fill example/level if missing; keep the existing translation.
            conn.execute(
                sa.text(
                    "UPDATE words SET example_sentence = COALESCE(example_sentence, :e), "
                    "level = COALESCE(level, 'A2') WHERE id = :id"
                ),
                {"e": example, "id": existing[0]},
            )
            word_ids.append(existing[0])
            continue
        row = conn.execute(
            sa.text(
                "INSERT INTO words (track, writing, normalized_word, translation, example_sentence, level) "
                "VALUES ('en', :w, :n, :t, :e, 'A2') RETURNING id"
            ),
            {"w": english, "n": n, "t": translation, "e": example},
        ).first()
        assert row is not None
        word_ids.append(row[0])

    pack_row = conn.execute(
        sa.text(
            "INSERT INTO packs (slug, track, title, description, category, words_count, is_active) "
            "VALUES (:slug, 'en', :title, :description, :category, :count, true) RETURNING id"
        ),
        {
            "slug": PACK["slug"], "title": PACK["title"], "description": PACK["description"],
            "category": PACK["category"], "count": len(PACK["words"]),
        },
    ).first()
    assert pack_row is not None
    for position, wid in enumerate(word_ids):
        conn.execute(
            sa.text(
                "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                "ON CONFLICT DO NOTHING"
            ),
            {"p": pack_row[0], "w": wid, "pos": position},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM pack_words WHERE pack_id IN (SELECT id FROM packs WHERE slug = :s)"
        ),
        {"s": PACK["slug"]},
    )
    conn.execute(sa.text("DELETE FROM packs WHERE slug = :s"), {"s": PACK["slug"]})
    # Leave the word rows (may be shared, e.g. haven't already existed).
