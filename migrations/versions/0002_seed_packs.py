"""seed sample packs

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


SAMPLE_PACKS = [
    {
        "slug": "crypto_basics",
        "title": "Crypto Basics",
        "description": "Базовые слова из мира криптовалют.",
        "category": "Crypto",
        "words": [
            ("wallet", "кошелёк"),
            ("blockchain", "блокчейн"),
            ("token", "токен"),
            ("ledger", "реестр"),
            ("miner", "майнер"),
            ("stake", "стейк"),
            ("yield", "доход"),
            ("exchange", "биржа"),
        ],
    },
    {
        "slug": "it_starter",
        "title": "IT Starter",
        "description": "Стартовый набор слов из IT.",
        "category": "IT",
        "words": [
            ("deploy", "развернуть"),
            ("commit", "коммит"),
            ("merge", "слияние"),
            ("branch", "ветка"),
            ("review", "ревью"),
            ("feature", "фича"),
            ("bug", "баг"),
            ("fix", "исправление"),
            ("release", "релиз"),
            ("test", "тест"),
            ("issue", "задача"),
            ("ship", "выпустить"),
            ("build", "сборка"),
        ],
    },
    {
        "slug": "business_basic",
        "title": "Business Basics",
        "description": "Базовые бизнес-слова.",
        "category": "Business",
        "words": [
            ("deadline", "дедлайн"),
            ("meeting", "встреча"),
            ("report", "отчёт"),
            ("client", "клиент"),
            ("stakeholder", "стейкхолдер"),
            ("budget", "бюджет"),
            ("revenue", "выручка"),
            ("profit", "прибыль"),
            ("growth", "рост"),
            ("trade", "торговля"),
        ],
    },
    {
        "slug": "travel_essentials",
        "title": "Travel Essentials",
        "description": "Слова для путешествий.",
        "category": "Travel",
        "words": [
            ("trip", "поездка"),
            ("flight", "рейс"),
            ("luggage", "багаж"),
            ("passport", "паспорт"),
            ("ticket", "билет"),
            ("hotel", "отель"),
            ("reservation", "бронь"),
            ("weather", "погода"),
            ("currency", "валюта"),
            ("souvenir", "сувенир"),
            ("delicious", "вкусный"),
        ],
    },
    {
        "slug": "basic_english_verbs",
        "title": "Basic English Verbs",
        "description": "Базовые английские глаголы.",
        "category": "Basic English",
        "words": [
            ("borrow", "брать в долг"),
            ("improve", "улучшать"),
            ("explain", "объяснять"),
            ("guess", "догадаться"),
            ("decide", "решать"),
            ("expect", "ожидать"),
            ("remember", "помнить"),
            ("forget", "забывать"),
            ("wait", "ждать"),
            ("arrive", "прибывать"),
            ("leave", "уходить"),
            ("stay", "оставаться"),
            ("spend", "тратить"),
            ("save", "сохранять"),
            ("lose", "терять"),
            ("win", "выигрывать"),
            ("learn", "учить"),
            ("teach", "учить (других)"),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for pack in SAMPLE_PACKS:
        word_ids: list[int] = []
        for english, translation in pack["words"]:
            normalized = english.strip().lower()
            # Upsert word.
            existing = conn.execute(
                sa.text("SELECT id FROM words WHERE normalized_word = :n"),
                {"n": normalized},
            ).first()
            if existing:
                word_ids.append(existing[0])
                continue
            row = conn.execute(
                sa.text(
                    "INSERT INTO words (english_word, normalized_word, translation) "
                    "VALUES (:e, :n, :t) RETURNING id"
                ),
                {"e": english, "n": normalized, "t": translation},
            ).first()
            assert row is not None
            word_ids.append(row[0])

        existing_pack = conn.execute(
            sa.text("SELECT id FROM packs WHERE slug = :slug"), {"slug": pack["slug"]}
        ).first()
        if existing_pack:
            continue
        pack_row = conn.execute(
            sa.text(
                "INSERT INTO packs (slug, title, description, category, words_count, is_active) "
                "VALUES (:slug, :title, :description, :category, :count, true) RETURNING id"
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
                    "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"p": pack_id, "w": wid, "pos": position},
            )


def downgrade() -> None:
    op.execute("DELETE FROM pack_words WHERE pack_id IN (SELECT id FROM packs WHERE slug IN ('crypto_basics','it_starter','business_basic','travel_essentials','basic_english_verbs'))")
    op.execute("DELETE FROM packs WHERE slug IN ('crypto_basics','it_starter','business_basic','travel_essentials','basic_english_verbs')")
