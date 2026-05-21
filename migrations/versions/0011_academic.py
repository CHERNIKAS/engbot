"""academic packs for IELTS/TOEFL (AWL core + IELTS trends)

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-21

Adds a new "Экзамены" group with two packs: a core Academic Word List
(distinct from the frequency levels) and an IELTS Task-1 vocabulary pack
for describing graphs/trends. Idempotent: words upserted by
(track, normalized), pack_words ON CONFLICT DO NOTHING, words_count = len.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

NEW_PACKS: list[dict] = [
    {
        "slug": "academic_awl",
        "title": "🎓 Academic Word List",
        "description": "Ядро академической лексики для IELTS/TOEFL — эссе, лекции, статьи.",
        "category": "Экзамены",
        "words": [
            ("analyze", "анализировать"), ("approach", "подход"), ("aspect", "аспект"),
            ("category", "категория"), ("concept", "концепция / понятие"), ("context", "контекст"),
            ("criteria", "критерии"), ("data", "данные"), ("environment", "окружающая среда"),
            ("establish", "устанавливать / основывать"), ("identify", "выявлять / определять"),
            ("interpret", "толковать / интерпретировать"), ("policy", "политика (курс)"),
            ("principle", "принцип"), ("region", "регион"), ("require", "требовать"),
            ("research", "исследование"), ("respond", "реагировать / отвечать"),
            ("section", "раздел"), ("sector", "сектор"), ("significant", "значимый"),
            ("theory", "теория"), ("vary", "варьироваться"), ("achieve", "достигать"),
            ("acquire", "приобретать"), ("assist", "помогать"), ("authority", "орган власти"),
            ("consist", "состоять (из)"), ("constitute", "составлять"),
            ("contribute", "вносить вклад"), ("coordinate", "координировать"),
            ("demonstrate", "демонстрировать"), ("dominate", "доминировать"),
            ("emphasis", "акцент / ударение"), ("focus", "сосредоточиться / фокус"),
            ("implement", "внедрять / реализовывать"), ("imply", "подразумевать"),
            ("initial", "первоначальный"), ("instance", "пример / случай"),
            ("invest", "инвестировать"), ("maintain", "поддерживать"),
            ("minimize", "минимизировать"), ("objective", "цель / объективный"),
            ("obtain", "получать"), ("occupy", "занимать"), ("option", "вариант"),
            ("participate", "участвовать"), ("perceive", "воспринимать"),
            ("potential", "потенциальный"), ("primary", "первичный / основной"),
            ("prior", "предшествующий"), ("procedure", "процедура"), ("promote", "продвигать"),
            ("proportion", "доля / пропорция"), ("publish", "публиковать"),
            ("regulate", "регулировать"), ("relevant", "уместный / релевантный"),
            ("restrict", "ограничивать"), ("reveal", "раскрывать"),
            ("sequence", "последовательность"), ("shift", "сдвиг / смена"),
            ("strategy", "стратегия"), ("sufficient", "достаточный"),
            ("summary", "краткое изложение"), ("survey", "опрос / обследование"),
            ("sustain", "выдерживать / сохранять"), ("technique", "приём / методика"),
            ("transfer", "передавать / переносить"), ("transform", "преобразовывать"),
            ("trend", "тенденция"), ("ultimate", "окончательный / предельный"),
            ("undertake", "предпринимать"), ("utilize", "использовать"), ("version", "версия"),
            ("via", "через / посредством"), ("volume", "объём"), ("welfare", "благосостояние"),
        ],
    },
    {
        "slug": "ielts_trends",
        "title": "📈 IELTS: графики и тренды",
        "description": "Описываем рост, спад и колебания в Task 1.",
        "category": "Экзамены",
        "words": [
            ("increase", "рост / увеличиваться"), ("decrease", "снижение / уменьшаться"),
            ("rise", "подъём / расти"), ("decline", "спад / снижаться"),
            ("drop", "падение / падать"), ("fluctuate", "колебаться"), ("peak", "пик"),
            ("plateau", "плато / выход на плато"), ("soar", "резко расти"),
            ("plummet", "резко падать"), ("surge", "всплеск / резкий рост"),
            ("dip", "небольшой спад"), ("steady", "устойчивый / стабильный"),
            ("gradual", "постепенный"), ("sharp", "резкий"),
            ("dramatic", "резкий / значительный"), ("slight", "незначительный"),
            ("substantial", "существенный"), ("approximately", "приблизительно"),
            ("respectively", "соответственно"), ("whereas", "тогда как"),
            ("figure", "цифра / показатель"), ("amount", "количество"),
        ],
    },
]


def _upsert_word(conn, english: str, translation: str) -> int:
    normalized = english.strip().lower()
    existing = conn.execute(
        sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"),
        {"n": normalized},
    ).first()
    if existing:
        return existing[0]
    row = conn.execute(
        sa.text(
            "INSERT INTO words (track, writing, normalized_word, translation) "
            "VALUES ('en', :w, :n, :t) RETURNING id"
        ),
        {"w": english, "n": normalized, "t": translation},
    ).first()
    assert row is not None
    return row[0]


def upgrade() -> None:
    conn = op.get_bind()
    for pack in NEW_PACKS:
        if conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": pack["slug"]}).first():
            continue
        word_ids = [_upsert_word(conn, en, ru) for en, ru in pack["words"]]
        row = conn.execute(
            sa.text(
                "INSERT INTO packs (slug, track, title, description, category, words_count, is_active) "
                "VALUES (:slug, 'en', :title, :description, :category, :count, true) RETURNING id"
            ),
            {
                "slug": pack["slug"], "title": pack["title"], "description": pack["description"],
                "category": pack["category"], "count": len(pack["words"]),
            },
        ).first()
        assert row is not None
        for position, wid in enumerate(word_ids):
            conn.execute(
                sa.text(
                    "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"p": row[0], "w": wid, "pos": position},
            )


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [p["slug"] for p in NEW_PACKS]
    conn.execute(
        sa.text(
            "DELETE FROM pack_words WHERE pack_id IN (SELECT id FROM packs WHERE slug IN :s)"
        ).bindparams(sa.bindparam("s", expanding=True)),
        {"s": slugs},
    )
    conn.execute(
        sa.text("DELETE FROM packs WHERE slug IN :s").bindparams(sa.bindparam("s", expanding=True)),
        {"s": slugs},
    )
