"""grammar foundation: topics + items + per-user progress, seed tenses

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-23

Adds the grammar content type (rule + choose-the-form exercises) and per-user
spaced-repetition progress (mirrors user_words so apply_review works unchanged).
Seeds the first pack — core tenses. Delivery into the course/push is wired
separately. Choice-only (no typing).
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


GRAMMAR: list[dict] = [
    {
        "slug": "tense_present_simple",
        "title": "Present Simple",
        "level": "A1",
        "position": 0,
        "rule": (
            "🟢 <b>Present Simple</b> — регулярные действия, привычки и факты.\n"
            "В 3-м лице ед. ч. (he/she/it) к глаголу добавляем <b>-s/-es</b>:\n"
            "I work → He work<b>s</b>."
        ),
        "items": [
            ("She ___ to school every day.", "goes", ["go", "going", "went"]),
            ("I ___ coffee in the morning.", "drink", ["drinks", "drinking", "drank"]),
            ("He ___ football on Sundays.", "plays", ["play", "playing", "played"]),
            ("They ___ in London.", "live", ["lives", "living", "lived"]),
            ("Water ___ at 100 degrees.", "boils", ["boil", "boiling", "boiled"]),
            ("My brother ___ three languages.", "speaks", ["speak", "speaking", "spoke"]),
            ("We usually ___ dinner at seven.", "have", ["has", "having", "had"]),
            ("It often ___ in autumn.", "rains", ["rain", "raining", "rained"]),
        ],
    },
    {
        "slug": "tense_present_continuous",
        "title": "Present Continuous",
        "level": "A1",
        "position": 1,
        "rule": (
            "🔵 <b>Present Continuous</b> — действие происходит <b>прямо сейчас</b>.\n"
            "Формула: <b>am/is/are + V-ing</b>.\n"
            "Look! She <b>is running</b>."
        ),
        "items": [
            ("Look! She ___ now.", "is running", ["runs", "run", "ran"]),
            ("I ___ a book at the moment.", "am reading", ["read", "reads", "reading"]),
            ("They ___ TV right now.", "are watching", ["watch", "watches", "watched"]),
            ("He ___ dinner now.", "is cooking", ["cooks", "cook", "cooked"]),
            ("We ___ for the bus.", "are waiting", ["wait", "waits", "waited"]),
            ("The baby ___ at the moment.", "is sleeping", ["sleeps", "sleep", "slept"]),
            ("Listen! Someone ___.", "is singing", ["sings", "sing", "sang"]),
            ("You ___ too fast.", "are driving", ["drive", "drives", "drove"]),
        ],
    },
    {
        "slug": "tense_past_simple",
        "title": "Past Simple",
        "level": "A2",
        "position": 2,
        "rule": (
            "🟠 <b>Past Simple</b> — завершённые действия в прошлом.\n"
            "Правильные глаголы: <b>+ed</b> (play → played).\n"
            "Неправильные — особые формы (go → went)."
        ),
        "items": [
            ("Yesterday I ___ to the cinema.", "went", ["go", "goes", "gone"]),
            ("She ___ a letter last week.", "wrote", ["writes", "write", "written"]),
            ("They ___ football on Monday.", "played", ["play", "plays", "playing"]),
            ("He ___ his keys yesterday.", "lost", ["loses", "lose", "losing"]),
            ("We ___ a great film last night.", "watched", ["watch", "watches", "watching"]),
            ("I ___ tired after work.", "was", ["is", "am", "were"]),
            ("The kids ___ at the park.", "were", ["was", "are", "is"]),
            ("She ___ breakfast at eight.", "had", ["has", "have", "having"]),
        ],
    },
    {
        "slug": "tense_future_will",
        "title": "Future (will)",
        "level": "A2",
        "position": 3,
        "rule": (
            "🟣 <b>Future с will</b> — решения, прогнозы и обещания.\n"
            "Формула: <b>will + базовая форма</b> глагола.\n"
            "I think it <b>will rain</b>."
        ),
        "items": [
            ("I think it ___ tomorrow.", "will rain", ["rains", "rained", "raining"]),
            ("She ___ you later.", "will call", ["calls", "called", "calling"]),
            ("We ___ at the airport at six.", "will arrive", ["arrive", "arrives", "arrived"]),
            ("Don't worry, I ___ you.", "will help", ["help", "helps", "helped"]),
            ("They ___ the match, I'm sure.", "will win", ["win", "wins", "won"]),
            ("He ___ here tomorrow.", "will be", ["is", "was", "been"]),
            ("I ___ a taxi to the station.", "will take", ["take", "takes", "took"]),
            ("Maybe we ___ to Spain next year.", "will travel", ["travel", "travels", "travelled"]),
        ],
    },
]


def upgrade() -> None:
    op.create_table(
        "grammar_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("track", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=8), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_grammar_topics_track", "grammar_topics", ["track"])

    op.create_table(
        "grammar_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("grammar_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("correct", sa.String(length=64), nullable=False),
        sa.Column("distractors", JSONB(), nullable=False, server_default="[]"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_grammar_items_topic", "grammar_items", ["topic_id"])

    op.create_table(
        "user_grammar_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grammar_item_id", sa.Integer(), sa.ForeignKey("grammar_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("ease_score", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("repetitions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mistakes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "grammar_item_id", name="uq_user_grammar_item"),
    )
    op.create_index("ix_user_grammar_items_user_status", "user_grammar_items", ["user_id", "status"])

    op.create_table(
        "user_grammar_topics",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("grammar_topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rule_seen_at", sa.DateTime(timezone=True), nullable=True),
    )

    conn = op.get_bind()
    for topic in GRAMMAR:
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
    op.drop_table("user_grammar_topics")
    op.drop_index("ix_user_grammar_items_user_status", table_name="user_grammar_items")
    op.drop_table("user_grammar_items")
    op.drop_index("ix_grammar_items_topic", table_name="grammar_items")
    op.drop_table("grammar_items")
    op.drop_index("ix_grammar_topics_track", table_name="grammar_topics")
    op.drop_table("grammar_topics")
