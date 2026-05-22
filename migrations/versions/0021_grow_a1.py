"""grow level A1 with common everyday words (vocab growth batch 1)

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-23

Vocabulary growth, curated (no NGSL file supplied, so frequency order is by
judgement). Adds ~90 common A1 words that were missing, each with a translation
and an example, tagged level=A1 and part_of_speech (inferred). Appended to the
level_a1 pack so the «🎓 Курс» spine extends automatically. Idempotent: words
deduped by normalized; pack links ON CONFLICT DO NOTHING; words_count recomputed.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.domain.pos import infer_part_of_speech

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

LEVEL_SLUG = "level_a1"
LEVEL = "A1"

# (english, translation, example)
NEW_WORDS: list[tuple[str, str, str]] = [
    # verbs
    ("listen", "слушать", "I listen to music every day."),
    ("watch", "смотреть", "We watched a film last night."),
    ("look", "смотреть / выглядеть", "Look at this picture."),
    ("talk", "разговаривать / болтать", "We talked for hours."),
    ("smile", "улыбаться", "She smiled at me."),
    ("laugh", "смеяться", "Everyone laughed at the joke."),
    ("cry", "плакать", "The baby started to cry."),
    ("jump", "прыгать", "The cat jumped on the table."),
    ("sing", "петь", "She sings in a choir."),
    ("climb", "взбираться / лезть", "We climbed the hill."),
    ("throw", "бросать", "Throw me the ball."),
    ("kick", "пинать / бить ногой", "He kicked the ball hard."),
    ("ride", "ездить верхом", "She rides a bike to work."),
    ("carry", "нести", "He carried the heavy bag."),
    ("pick", "срывать / собирать", "She picked apples from the tree."),
    ("wake", "просыпаться / будить", "I wake up at seven."),
    ("rest", "отдыхать", "Let's rest for a while."),
    ("hurt", "болеть / причинять боль", "My leg hurts."),
    ("swim", "плавать", "We swam in the lake."),
    ("cut", "резать", "Cut the bread, please."),
    ("hit", "ударять", "He hit the ball."),
    ("visit", "навещать", "We visited our grandmother."),
    ("finish", "заканчивать", "I finished my work."),
    ("worry", "беспокоиться", "Don't worry about it."),
    ("wish", "желать", "I wish you luck."),
    ("smell", "пахнуть / нюхать", "The flowers smell nice."),
    ("taste", "пробовать на вкус", "Taste the soup."),
    ("enter", "входить", "Please enter the room."),
    ("plan", "планировать", "We plan to travel in June."),
    ("check", "проверять", "Check your answers."),
    ("change", "менять", "I changed my plans."),
    ("follow", "следовать", "Follow me, please."),
    ("lead", "вести", "She leads the team."),
    ("return", "возвращаться / возвращать", "He returned home late."),
    ("happen", "случаться", "What happened here?"),
    ("marry", "жениться / выходить замуж", "They married last year."),
    ("bake", "печь (выпекать)", "She bakes bread on Sundays."),
    # nouns
    ("town", "городок", "She lives in a small town."),
    ("village", "деревня", "My grandparents live in a village."),
    ("country", "страна", "France is a beautiful country."),
    ("world", "мир (свет)", "English is spoken around the world."),
    ("sea", "море", "We swam in the sea."),
    ("beach", "пляж", "The beach was crowded."),
    ("mountain", "гора", "They climbed the mountain."),
    ("river", "река", "The river flows to the sea."),
    ("forest", "лес", "We walked through the forest."),
    ("lake", "озеро", "The lake froze in winter."),
    ("field", "поле", "Cows grazed in the field."),
    ("animal", "животное", "A dog is a friendly animal."),
    ("weekend", "выходные", "We relax on the weekend."),
    ("birthday", "день рождения", "Happy birthday to you!"),
    ("gift", "подарок", "She gave me a nice gift."),
    ("shop", "магазин", "I bought milk at the shop."),
    ("market", "рынок", "We buy fruit at the market."),
    ("restaurant", "ресторан", "We had dinner at a restaurant."),
    ("story", "история / рассказ", "She told us a funny story."),
    ("song", "песня", "This is my favourite song."),
    ("film", "фильм", "Let's watch a film tonight."),
    ("toy", "игрушка", "The child played with a toy."),
    ("roof", "крыша", "Snow covered the roof."),
    ("colour", "цвет", "Blue is my favourite colour."),
    ("meal", "приём пищи", "We had a big meal."),
    ("neighbour", "сосед", "My neighbour is very friendly."),
    # adjectives
    ("young", "молодой", "She is too young to drive."),
    ("tall", "высокий (рослый)", "He is a tall man."),
    ("fat", "толстый", "The cat is a bit fat."),
    ("thin", "тонкий / худой", "The ice is very thin."),
    ("full", "полный", "The glass is full."),
    ("soft", "мягкий", "The pillow is very soft."),
    ("heavy", "тяжёлый", "This box is heavy."),
    ("bright", "яркий", "The sun is very bright."),
    ("loud", "громкий", "The music is too loud."),
    ("near", "близкий", "The shop is near."),
    ("hungry", "голодный", "I am very hungry."),
    ("thirsty", "испытывающий жажду", "I am thirsty, give me water."),
    ("tired", "уставший", "I feel tired today."),
    ("busy", "занятой", "She is busy at work."),
    ("free", "свободный", "Are you free tonight?"),
    ("funny", "смешной", "That joke was funny."),
    ("interesting", "интересный", "The book is interesting."),
    ("ugly", "уродливый", "The old building is ugly."),
    ("poor", "бедный", "They were poor but happy."),
    ("true", "правдивый / верный", "Is the story true?"),
    ("real", "настоящий", "Is this a real diamond?"),
    ("same", "одинаковый / тот же", "We have the same bag."),
    ("next", "следующий", "See you next week."),
    ("dry", "сухой", "The towel is dry."),
    ("wet", "мокрый", "The grass is wet."),
    ("deep", "глубокий", "The lake is deep."),
    ("wide", "широкий", "The road is wide."),
    ("narrow", "узкий", "The street is narrow."),
]

# Keep translations distinct: these existing words otherwise collide with new
# ones above (deep/profound, wide/broad). (normalized, old, new)
CROSS_EDITS: list[tuple[str, str, str]] = [
    ("profound", "глубокий", "глубокий (основательный)"),
    ("broad", "широкий", "широкий / обширный"),
]


def upgrade() -> None:
    conn = op.get_bind()
    pack = conn.execute(
        sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}
    ).first()
    if pack is None:
        return
    pack_id = pack[0]
    pos = conn.execute(
        sa.text("SELECT COALESCE(max(position), -1) + 1 FROM pack_words WHERE pack_id = :p"),
        {"p": pack_id},
    ).scalar()

    for english, translation, example in NEW_WORDS:
        n = english.strip().lower()
        row = conn.execute(
            sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"),
            {"n": n},
        ).first()
        if row:
            wid = row[0]
            conn.execute(
                sa.text(
                    "UPDATE words SET level = COALESCE(level, :l), "
                    "example_sentence = COALESCE(example_sentence, :e), "
                    "part_of_speech = COALESCE(part_of_speech, :pos) WHERE id = :id"
                ),
                {"l": LEVEL, "e": example, "pos": infer_part_of_speech(translation), "id": wid},
            )
        else:
            wid = conn.execute(
                sa.text(
                    "INSERT INTO words (track, writing, normalized_word, translation, "
                    "example_sentence, level, part_of_speech) VALUES "
                    "('en', :w, :n, :t, :e, :l, :pos) RETURNING id"
                ),
                {
                    "w": english, "n": n, "t": translation, "e": example,
                    "l": LEVEL, "pos": infer_part_of_speech(translation),
                },
            ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                "ON CONFLICT DO NOTHING"
            ),
            {"p": pack_id, "w": wid, "pos": pos},
        )
        pos += 1

    conn.execute(
        sa.text("UPDATE packs SET words_count = (SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"),
        {"p": pack_id},
    )

    edit = sa.text(
        "UPDATE words SET translation = :new WHERE track = 'en' AND normalized_word = :n AND translation = :old"
    )
    for normalized, old, new in CROSS_EDITS:
        conn.execute(edit, {"n": normalized, "old": old, "new": new})


def downgrade() -> None:
    conn = op.get_bind()
    edit = sa.text(
        "UPDATE words SET translation = :old WHERE track = 'en' AND normalized_word = :n AND translation = :new"
    )
    for normalized, old, new in CROSS_EDITS:
        conn.execute(edit, {"n": normalized, "old": old, "new": new})
    names = [w[0].strip().lower() for w in NEW_WORDS]
    pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}).first()
    # Delete the word rows we created (cascades to pack_words / user_words).
    conn.execute(
        sa.text("DELETE FROM words WHERE track = 'en' AND normalized_word IN :n").bindparams(
            sa.bindparam("n", expanding=True)
        ),
        {"n": names},
    )
    if pack is not None:
        conn.execute(
            sa.text("UPDATE packs SET words_count = (SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"),
            {"p": pack[0]},
        )
