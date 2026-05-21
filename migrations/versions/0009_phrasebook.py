"""phrasebook packs (situational phrases) under «Фразы»

Revision ID: 0009
Revises: 0008
Create Date: 2025-01-12

Ready-to-use phrases by situation. Multi-word entries are recognition-only in
study (cleared after QUIZ, no typing) — handled by the drill, no schema change.
Idempotent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

PACKS: list[dict] = [
    {
        "slug": "phrases_small_talk",
        "title": "Small talk",
        "description": "Повседневные фразы для общения.",
        "category": "Фразы",
        "words": [
            ("How are you?", "Как дела?"),
            ("Nice to meet you", "Приятно познакомиться"),
            ("What's up?", "Как оно? / Что нового?"),
            ("See you later", "Увидимся позже"),
            ("Take care", "Береги себя"),
            ("What do you mean?", "Что ты имеешь в виду?"),
            ("I don't understand", "Я не понимаю"),
            ("Could you repeat that?", "Можешь повторить?"),
            ("No problem", "Без проблем"),
            ("You're welcome", "Пожалуйста (в ответ на спасибо)"),
            ("Excuse me", "Извините (привлечь внимание)"),
            ("I'm sorry", "Извини / Мне жаль"),
            ("It depends", "Смотря как / зависит"),
            ("Of course", "Конечно"),
            ("Never mind", "Неважно / забей"),
            ("Sounds good", "Звучит хорошо"),
        ],
    },
    {
        "slug": "phrases_travel",
        "title": "Аэропорт и путешествия",
        "description": "Фразы для поездок.",
        "category": "Фразы",
        "words": [
            ("Where is the gate?", "Где выход на посадку?"),
            ("I have a reservation", "У меня есть бронь"),
            ("How much is it?", "Сколько это стоит?"),
            ("Where is the bathroom?", "Где туалет?"),
            ("I'm lost", "Я заблудился"),
            ("Can you help me?", "Можешь помочь?"),
            ("One ticket, please", "Один билет, пожалуйста"),
            ("Is this seat taken?", "Это место занято?"),
            ("What time is the flight?", "Во сколько рейс?"),
            ("I'd like to check in", "Я хочу зарегистрироваться"),
            ("Do you speak English?", "Вы говорите по-английски?"),
            ("Turn left", "Поверните налево"),
            ("Turn right", "Поверните направо"),
            ("Go straight", "Идите прямо"),
        ],
    },
    {
        "slug": "phrases_restaurant",
        "title": "Ресторан",
        "description": "Фразы для кафе и ресторанов.",
        "category": "Фразы",
        "words": [
            ("A table for two", "Столик на двоих"),
            ("The menu, please", "Меню, пожалуйста"),
            ("I'd like to order", "Я хочу заказать"),
            ("What do you recommend?", "Что посоветуете?"),
            ("The bill, please", "Счёт, пожалуйста"),
            ("Is it spicy?", "Это острое?"),
            ("I'm a vegetarian", "Я вегетарианец"),
            ("Water, please", "Воды, пожалуйста"),
            ("It's delicious", "Очень вкусно"),
            ("No ice, please", "Без льда, пожалуйста"),
            ("I'm allergic to nuts", "У меня аллергия на орехи"),
            ("Can I pay by card?", "Можно оплатить картой?"),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for pack in PACKS:
        if conn.execute(
            sa.text("SELECT id FROM packs WHERE slug = :slug"), {"slug": pack["slug"]}
        ).first():
            continue
        word_ids: list[int] = []
        for english, translation in pack["words"]:
            normalized = english.strip().lower()
            existing = conn.execute(
                sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"),
                {"n": normalized},
            ).first()
            if existing:
                word_ids.append(existing[0])
                continue
            row = conn.execute(
                sa.text(
                    "INSERT INTO words (track, writing, normalized_word, translation) "
                    "VALUES ('en', :w, :n, :t) RETURNING id"
                ),
                {"w": english, "n": normalized, "t": translation},
            ).first()
            assert row is not None
            word_ids.append(row[0])

        pack_row = conn.execute(
            sa.text(
                "INSERT INTO packs (slug, track, title, description, category, words_count, is_active) "
                "VALUES (:slug, 'en', :title, :description, :category, :count, true) RETURNING id"
            ),
            {
                "slug": pack["slug"],
                "title": pack["title"],
                "description": pack["description"],
                "category": pack["category"],
                "count": len(pack["words"]),
            },
        ).first()
        assert pack_row is not None
        pack_id = pack_row[0]
        for position, wid in enumerate(word_ids):
            conn.execute(
                sa.text(
                    "INSERT INTO pack_words (pack_id, word_id, position) "
                    "VALUES (:p, :w, :pos) ON CONFLICT DO NOTHING"
                ),
                {"p": pack_id, "w": wid, "pos": position},
            )


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [p["slug"] for p in PACKS]
    conn.execute(
        sa.text(
            "DELETE FROM pack_words WHERE pack_id IN (SELECT id FROM packs WHERE slug IN :slugs)"
        ).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": slugs},
    )
    conn.execute(
        sa.text("DELETE FROM packs WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", expanding=True)
        ),
        {"slugs": slugs},
    )
