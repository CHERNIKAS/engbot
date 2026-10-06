"""Phrases get their colloquial rendering, and learners choose which to learn.

«Could you repeat that?» is what a phrasebook says; «Come again?» is what a
friend says. Twenty-five of the 102 phrases have a common colloquial rendering
worth knowing (reviewed by the owner, 2026-10-06); the rest are said the same
way in any register. `words.colloquial` holds it with a short note on tone, and
`user_words.phrase_style` remembers what the learner chose: neutral, casual or
both — NULL until they are asked.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

VARIANTS = [
    ("How are you?", "How's it going?", "по-дружески, уместно почти везде"),
    ("See you later", "Catch you later", "со знакомыми"),
    ("I don't understand", "I don't get it", "очень частое, разговорное"),
    ("Could you repeat that?", "Come again?", "со своими; может прозвучать резко"),
    ("No problem", "No worries", "дружелюбно"),
    ("You're welcome", "Anytime", "тепло, «обращайся»"),
    ("I'm sorry", "My bad", "только за мелкий косяк, не для серьёзных извинений"),
    ("Of course", "Sure", "коротко"),
    ("Never mind", "Forget it", "бывает с ноткой обиды"),
    ("Sounds good", "Works for me", "когда договариваетесь"),
    ("Can you help me?", "Could you give me a hand?", "«подсобишь?»"),
    ("I'd like to order", "Can I get...?", "в кафе, особенно в США"),
    ("What do you recommend?", "What's good here?", "официанту, дружелюбно"),
    ("It's delicious", "This is so good", "живая реакция"),
    ("The Wi-Fi isn't working", "The Wi-Fi's down", "разговорно"),
    ("I don't feel well", "I'm feeling under the weather", "мягко, «что-то я расклеился»"),
    ("I've caught a cold", "I've got a cold", "проще"),
    ("I'm just looking", "Just browsing", "в магазине"),
    ("It's too expensive", "That's a bit pricey", "мягче и вежливее"),
    ("Can I get a discount?", "Any chance of a discount?", "непринуждённо"),
    ("Who's calling?", "Who's this?", "резче, со своими"),
    ("Hold on, please", "Hang on a sec", "разговорно"),
    ("He's not available right now", "He's not around right now", "разговорно"),
    ("I can't hear you well", "You're breaking up", "про плохую связь"),
    ("My battery is dying", "My phone's about to die", "разговорно"),
]


def upgrade() -> None:
    op.add_column("words", sa.Column("colloquial", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("colloquial_note", sa.Text(), nullable=True))
    op.add_column("user_words", sa.Column("phrase_style", sa.String(8), nullable=True))
    bind = op.get_bind()
    for writing, colloquial, note in VARIANTS:
        bind.execute(
            sa.text(
                "update words set colloquial = :c, colloquial_note = :n"
                " where is_phrase and writing = :w"
            ),
            {"c": colloquial, "n": note, "w": writing},
        )


def downgrade() -> None:
    op.drop_column("user_words", "phrase_style")
    op.drop_column("words", "colloquial_note")
    op.drop_column("words", "colloquial")
