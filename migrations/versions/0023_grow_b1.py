"""grow level B1 with common intermediate words (vocab growth batch 3)

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-23

Curated growth (no NGSL file). ~90 common B1 words that were missing, each with
translation + example, level=B1 + inferred POS, appended to level_b1. Translations
chosen distinct from existing ones to avoid synonym collisions. Idempotent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.domain.pos import infer_part_of_speech

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

LEVEL_SLUG = "level_b1"
LEVEL = "B1"

NEW_WORDS: list[tuple[str, str, str]] = [
    # verbs
    ("arrest", "арестовывать", "Police arrested the thief."),
    ("compete", "соревноваться", "They compete for the prize."),
    ("deal", "иметь дело", "We deal with many clients."),
    ("defend", "оборонять", "Soldiers defend the city."),
    ("deserve", "заслуживать", "You deserve a rest."),
    ("disturb", "мешать / беспокоить", "Please don't disturb me."),
    ("doubt", "сомневаться", "I doubt it's true."),
    ("employ", "нанимать (на работу)", "The factory employs 200 people."),
    ("export", "экспортировать", "They export coffee abroad."),
    ("import", "импортировать", "We import cars from Japan."),
    ("intend", "намереваться", "I intend to learn French."),
    ("judge", "судить", "Don't judge people too fast."),
    ("mention", "упоминать", "She mentioned your name."),
    ("obey", "подчиняться", "Drivers must obey the rules."),
    ("own", "владеть", "They own a small shop."),
    ("pretend", "притворяться", "He pretended to sleep."),
    ("recall", "припоминать", "I can't recall his name."),
    ("reflect", "отражать", "The lake reflects the sky."),
    ("regret", "сожалеть", "I regret my words."),
    ("reject", "отвергать", "They rejected the offer."),
    ("relate", "относиться / связывать", "How does this relate to us?"),
    ("remove", "удалять", "Remove the old files."),
    ("reserve", "бронировать", "I reserved a table for two."),
    ("search", "обыскивать / поиск", "They searched the whole house."),
    ("settle", "улаживать / поселяться", "They settled in Canada."),
    ("suffer", "страдать", "He suffers from headaches."),
    ("supply", "снабжать / поставка", "They supply fresh fish."),
    ("tend", "иметь тенденцию", "Prices tend to rise."),
    ("treat", "обращаться / угощать", "Treat others with respect."),
    ("translate", "переводить", "Can you translate this letter?"),
    # nouns
    ("advice", "совет", "She gave me good advice."),
    ("cause", "причина", "What was the cause of the fire?"),
    ("choice", "выбор", "It's your choice."),
    ("crime", "преступление", "Crime is rising in the city."),
    ("damage", "ущерб / повреждение", "The storm caused damage."),
    ("danger", "опасность", "Smoking is a danger to health."),
    ("emotion", "эмоция", "He showed no emotion."),
    ("energy", "энергия", "Solar energy is clean."),
    ("event", "событие", "The wedding was a happy event."),
    ("failure", "неудача / провал", "The plan was a failure."),
    ("fault", "вина / дефект", "It was not my fault."),
    ("freedom", "свобода", "They fought for freedom."),
    ("habit", "привычка", "Smoking is a bad habit."),
    ("honesty", "честность", "I value honesty."),
    ("lack", "нехватка", "There is a lack of water."),
    ("level", "уровень", "The water level rose."),
    ("luck", "удача / везение", "Good luck on your exam!"),
    ("mood", "настроение", "She is in a good mood."),
    ("nature", "природа", "We love walking in nature."),
    ("patience", "терпение", "Teaching requires patience."),
    ("peace", "мир (покой)", "I just want some peace."),
    ("power", "сила / власть", "Knowledge is power."),
    ("pride", "гордость", "She felt pride in her work."),
    ("reason", "довод / причина", "Give me one good reason."),
    ("result", "результат", "The result was a surprise."),
    ("safety", "безопасность", "Safety comes first."),
    ("silence", "тишина / молчание", "There was a long silence."),
    ("truth", "правда / истина", "Tell me the truth."),
    ("victory", "победа", "The team celebrated the victory."),
    ("wealth", "богатство", "Health is more important than wealth."),
    ("topic", "тема", "Let's change the topic."),
    ("fact", "факт", "That's a well-known fact."),
    # adjectives
    ("alive", "живой", "The fish is still alive."),
    ("alone", "один (в одиночестве)", "She lives alone."),
    ("asleep", "спящий", "The baby is asleep."),
    ("basic", "базовый", "These are basic rules."),
    ("certain", "определённый", "There are certain rules to follow."),
    ("equal", "равный", "Everyone is equal here."),
    ("familiar", "знакомый", "The song sounds familiar."),
    ("formal", "формальный", "Write a formal letter."),
    ("guilty", "виноватый", "He felt guilty about it."),
    ("honest", "честный", "She is an honest person."),
    ("ideal", "идеальный", "This is the ideal spot."),
    ("legal", "законный / легальный", "Is this legal?"),
    ("mental", "умственный / психический", "Mental health is important."),
    ("normal", "нормальный", "This is normal behaviour."),
    ("official", "официальный", "We await an official statement."),
    ("perfect", "совершенный / безупречный", "Her English is perfect."),
    ("physical", "физический", "Physical exercise is healthy."),
    ("private", "частный / личный", "This is a private matter."),
    ("public", "публичный / общественный", "We met in a public park."),
    ("pure", "чистый (без примесей)", "This is pure gold."),
    ("serious", "серьёзный", "This is a serious problem."),
    ("silent", "безмолвный", "He stayed silent all evening."),
    ("single", "единственный / одиночный", "Not a single person came."),
    ("social", "социальный / общественный", "Humans are social animals."),
    ("tiny", "крошечный", "A tiny insect crawled by."),
    ("usual", "обычный / привычный", "We met at the usual place."),
    ("worth", "стоящий", "It's worth a try."),
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
