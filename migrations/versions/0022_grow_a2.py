"""grow level A2 with common everyday words (vocab growth batch 2)

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-23

Curated growth (no NGSL file). ~80 common A2 words that were missing, each with
translation + example, level=A2 + inferred POS, appended to level_a2 (extends the
course spine). Idempotent; words deduped by normalized; words_count recomputed.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.domain.pos import infer_part_of_speech

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

LEVEL_SLUG = "level_a2"
LEVEL = "A2"

NEW_WORDS: list[tuple[str, str, str]] = [
    # verbs
    ("knock", "стучать", "Someone knocked on the door."),
    ("lock", "запирать", "Lock the door before you leave."),
    ("shut", "захлопывать", "Please shut the window."),
    ("hang", "вешать", "Hang your coat here."),
    ("boil", "кипятить", "Boil the water for tea."),
    ("fry", "жарить", "Fry the eggs in butter."),
    ("serve", "подавать (еду)", "They serve breakfast at eight."),
    ("feed", "кормить", "I feed the cat every morning."),
    ("plant", "сажать (растение)", "We planted a tree in the garden."),
    ("shake", "трясти", "Shake the bottle before use."),
    ("wave", "махать рукой", "She waved at her friend."),
    ("bite", "кусать", "The dog never bites."),
    ("chew", "жевать", "Chew your food slowly."),
    ("whistle", "свистеть", "He whistled a happy tune."),
    ("sneeze", "чихать", "Dust makes me sneeze."),
    ("knit", "вязать", "Grandma knits warm socks."),
    ("sew", "шить", "She sewed a button on the shirt."),
    ("iron", "гладить утюгом", "I need to iron my shirt."),
    ("sweep", "подметать", "He swept the floor."),
    ("wipe", "вытирать", "Wipe the table, please."),
    ("greet", "приветствовать", "She greeted us with a smile."),
    ("warn", "предупреждать", "I warned him about the ice."),
    ("remind", "напоминать", "Remind me to call her."),
    ("advise", "советовать", "The doctor advised more rest."),
    ("promise", "обещать", "I promise to come back."),
    ("whisper", "шептать", "She whispered a secret."),
    ("scream", "вопить", "The crowd screamed with joy."),
    ("chat", "болтать", "We chatted over coffee."),
    # nouns
    ("ground", "земля (поверхность)", "He sat on the ground."),
    ("grass", "трава", "The grass is wet with dew."),
    ("tree", "дерево", "A bird sat in the tree."),
    ("flower", "цветок", "She picked a yellow flower."),
    ("leaf", "лист (растения)", "A leaf fell from the tree."),
    ("stone", "камень", "He threw a stone into the lake."),
    ("sand", "песок", "The kids played in the sand."),
    ("island", "остров", "They live on a small island."),
    ("hill", "холм", "Our house is on a hill."),
    ("valley", "долина", "The river runs through the valley."),
    ("cave", "пещера", "Bats live in the cave."),
    ("coast", "побережье", "We drove along the coast."),
    ("fence", "забор", "The dog jumped over the fence."),
    ("yard", "двор", "The children play in the yard."),
    ("noise", "шум", "The noise kept me awake."),
    ("voice", "голос", "She has a beautiful voice."),
    ("sound", "звук", "I heard a strange sound."),
    ("view", "вид (пейзаж)", "The view from the top is amazing."),
    ("shape", "форма", "The cloud has a funny shape."),
    ("size", "размер", "What size do you wear?"),
    ("weight", "вес", "The weight of the bag is heavy."),
    ("height", "высота", "The height of the tower is 100 metres."),
    ("length", "длина", "Measure the length of the room."),
    ("speed", "скорость", "The car slowed its speed."),
    ("distance", "расстояние", "It's a short distance to the shop."),
    ("piece", "кусок", "Have a piece of cake."),
    ("group", "группа", "A group of tourists arrived."),
    ("list", "список", "Make a shopping list."),
    ("note", "заметка", "She left a note on the desk."),
    ("mark", "отметка", "He got a high mark on the test."),
    ("line", "линия / очередь", "Stand in the line, please."),
    ("edge", "край", "Don't stand near the edge."),
    ("middle", "середина", "He sat in the middle of the room."),
    ("side", "сторона", "Write on one side of the page."),
    # adjectives
    ("safe", "безопасный", "This area is safe at night."),
    ("rude", "грубый", "It is rude to interrupt."),
    ("friendly", "дружелюбный", "Our neighbours are very friendly."),
    ("shy", "застенчивый", "He is too shy to speak."),
    ("stupid", "глупый", "That was a stupid mistake."),
    ("crazy", "сумасшедший", "That's a crazy idea."),
    ("ancient", "древний", "We visited an ancient temple."),
    ("fresh", "свежий", "I bought fresh bread."),
    ("sweet", "сладкий", "This tea is too sweet."),
    ("sour", "кислый", "The lemon is very sour."),
    ("bitter", "горький", "Black coffee tastes bitter."),
    ("salty", "солёный", "The soup is too salty."),
    ("spicy", "острый (о еде)", "I love spicy food."),
    ("cool", "прохладный", "The evening was cool and pleasant."),
    ("smooth", "гладкий", "The table has a smooth surface."),
    ("rough", "шершавый", "The rock felt rough."),
    ("thick", "густой", "She made a thick soup."),
    ("smart", "сообразительный", "She is a smart student."),
    ("gentle", "нежный", "He has a gentle voice."),
    ("strict", "строгий", "Our teacher is very strict."),
]


def upgrade() -> None:
    conn = op.get_bind()
    pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}).first()
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
            sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"), {"n": n}
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
                {"w": english, "n": n, "t": translation, "e": example, "l": LEVEL,
                 "pos": infer_part_of_speech(translation)},
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


def downgrade() -> None:
    conn = op.get_bind()
    names = [w[0].strip().lower() for w in NEW_WORDS]
    pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": LEVEL_SLUG}).first()
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
