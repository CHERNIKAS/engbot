"""seed curated content packs (irregular/phrasal verbs + themes)

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-08

Hand-curated EN→RU packs with verified translations. Irregular verbs carry their
three forms in the example field. All track='en'. Idempotent: existing words
(by track+normalized) and packs (by slug) are reused/skipped.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


# Each pack: slug, title, description, category, words.
# A word is (english, translation) or (english, translation, example).
PACKS: list[dict] = [
    {
        "slug": "irregular_verbs_core",
        "title": "Неправильные глаголы",
        "description": "Самые частые неправильные глаголы с тремя формами.",
        "category": "Грамматика",
        "words": [
            ("be", "быть", "be – was/were – been"),
            ("have", "иметь", "have – had – had"),
            ("do", "делать", "do – did – done"),
            ("say", "говорить", "say – said – said"),
            ("go", "идти / ехать", "go – went – gone"),
            ("get", "получать", "get – got – got/gotten"),
            ("make", "делать / создавать", "make – made – made"),
            ("know", "знать", "know – knew – known"),
            ("think", "думать", "think – thought – thought"),
            ("take", "брать", "take – took – taken"),
            ("see", "видеть", "see – saw – seen"),
            ("come", "приходить", "come – came – come"),
            ("find", "находить", "find – found – found"),
            ("give", "давать", "give – gave – given"),
            ("tell", "рассказывать", "tell – told – told"),
            ("become", "становиться", "become – became – become"),
            ("show", "показывать", "show – showed – shown"),
            ("leave", "уходить / оставлять", "leave – left – left"),
            ("feel", "чувствовать", "feel – felt – felt"),
            ("bring", "приносить", "bring – brought – brought"),
            ("begin", "начинать", "begin – began – begun"),
            ("keep", "хранить / держать", "keep – kept – kept"),
            ("hold", "держать", "hold – held – held"),
            ("write", "писать", "write – wrote – written"),
            ("stand", "стоять", "stand – stood – stood"),
            ("hear", "слышать", "hear – heard – heard"),
            ("let", "позволять", "let – let – let"),
            ("mean", "значить", "mean – meant – meant"),
            ("set", "устанавливать", "set – set – set"),
            ("meet", "встречать", "meet – met – met"),
            ("run", "бежать", "run – ran – run"),
            ("pay", "платить", "pay – paid – paid"),
            ("sit", "сидеть", "sit – sat – sat"),
            ("speak", "говорить", "speak – spoke – spoken"),
            ("read", "читать", "read – read – read"),
            ("buy", "покупать", "buy – bought – bought"),
            ("send", "отправлять", "send – sent – sent"),
            ("build", "строить", "build – built – built"),
            ("understand", "понимать", "understand – understood – understood"),
            ("draw", "рисовать", "draw – drew – drawn"),
            ("break", "ломать", "break – broke – broken"),
            ("spend", "тратить", "spend – spent – spent"),
            ("eat", "есть", "eat – ate – eaten"),
            ("drink", "пить", "drink – drank – drunk"),
            ("drive", "водить", "drive – drove – driven"),
            ("sell", "продавать", "sell – sold – sold"),
            ("win", "выигрывать", "win – won – won"),
            ("teach", "учить (других)", "teach – taught – taught"),
            ("catch", "ловить", "catch – caught – caught"),
            ("sleep", "спать", "sleep – slept – slept"),
        ],
    },
    {
        "slug": "phrasal_verbs_core",
        "title": "Фразовые глаголы",
        "description": "Базовые фразовые глаголы.",
        "category": "Грамматика",
        "words": [
            ("give up", "сдаваться"),
            ("find out", "выяснять"),
            ("look for", "искать"),
            ("look after", "заботиться"),
            ("look forward to", "ждать с нетерпением"),
            ("come back", "возвращаться"),
            ("go on", "продолжать"),
            ("turn on", "включать"),
            ("turn off", "выключать"),
            ("put on", "надевать"),
            ("take off", "снимать / взлетать"),
            ("get up", "вставать"),
            ("wake up", "просыпаться"),
            ("set up", "настраивать"),
            ("pick up", "поднимать / забирать"),
            ("grow up", "взрослеть"),
            ("run out", "заканчиваться"),
            ("break down", "ломаться"),
            ("show up", "появляться"),
            ("figure out", "разобраться"),
        ],
    },
    {
        "slug": "theme_colors",
        "title": "Цвета",
        "description": "Основные цвета.",
        "category": "Темы",
        "words": [
            ("red", "красный"),
            ("orange", "оранжевый"),
            ("yellow", "жёлтый"),
            ("green", "зелёный"),
            ("blue", "синий"),
            ("purple", "фиолетовый"),
            ("pink", "розовый"),
            ("brown", "коричневый"),
            ("black", "чёрный"),
            ("white", "белый"),
            ("grey", "серый"),
            ("gold", "золотой"),
        ],
    },
    {
        "slug": "theme_family",
        "title": "Семья",
        "description": "Члены семьи.",
        "category": "Темы",
        "words": [
            ("mother", "мать"),
            ("father", "отец"),
            ("parent", "родитель"),
            ("son", "сын"),
            ("daughter", "дочь"),
            ("brother", "брат"),
            ("sister", "сестра"),
            ("grandmother", "бабушка"),
            ("grandfather", "дедушка"),
            ("husband", "муж"),
            ("wife", "жена"),
            ("child", "ребёнок"),
            ("uncle", "дядя"),
            ("aunt", "тётя"),
            ("cousin", "двоюродный брат/сестра"),
            ("relative", "родственник"),
        ],
    },
    {
        "slug": "theme_body",
        "title": "Тело",
        "description": "Части тела.",
        "category": "Темы",
        "words": [
            ("head", "голова"),
            ("hair", "волосы"),
            ("face", "лицо"),
            ("eye", "глаз"),
            ("ear", "ухо"),
            ("nose", "нос"),
            ("mouth", "рот"),
            ("tooth", "зуб"),
            ("neck", "шея"),
            ("shoulder", "плечо"),
            ("arm", "рука (от плеча)"),
            ("hand", "кисть руки"),
            ("finger", "палец"),
            ("chest", "грудь"),
            ("back", "спина"),
            ("stomach", "живот"),
            ("leg", "нога"),
            ("knee", "колено"),
            ("foot", "ступня"),
            ("heart", "сердце"),
            ("brain", "мозг"),
            ("skin", "кожа"),
        ],
    },
    {
        "slug": "theme_food",
        "title": "Еда",
        "description": "Базовые слова о еде.",
        "category": "Темы",
        "words": [
            ("bread", "хлеб"),
            ("milk", "молоко"),
            ("cheese", "сыр"),
            ("butter", "масло"),
            ("egg", "яйцо"),
            ("meat", "мясо"),
            ("chicken", "курица"),
            ("fish", "рыба"),
            ("rice", "рис"),
            ("soup", "суп"),
            ("salad", "салат"),
            ("fruit", "фрукт"),
            ("apple", "яблоко"),
            ("banana", "банан"),
            ("grape", "виноград"),
            ("vegetable", "овощ"),
            ("potato", "картофель"),
            ("tomato", "помидор"),
            ("onion", "лук"),
            ("sugar", "сахар"),
            ("salt", "соль"),
            ("water", "вода"),
            ("tea", "чай"),
            ("coffee", "кофе"),
            ("juice", "сок"),
            ("breakfast", "завтрак"),
            ("lunch", "обед"),
            ("dinner", "ужин"),
        ],
    },
    {
        "slug": "theme_time",
        "title": "Время и дни",
        "description": "Дни недели, месяцы, время.",
        "category": "Темы",
        "words": [
            ("Monday", "понедельник"),
            ("Tuesday", "вторник"),
            ("Wednesday", "среда"),
            ("Thursday", "четверг"),
            ("Friday", "пятница"),
            ("Saturday", "суббота"),
            ("Sunday", "воскресенье"),
            ("today", "сегодня"),
            ("tomorrow", "завтра"),
            ("yesterday", "вчера"),
            ("morning", "утро"),
            ("afternoon", "день (после полудня)"),
            ("evening", "вечер"),
            ("night", "ночь"),
            ("week", "неделя"),
            ("month", "месяц"),
            ("year", "год"),
            ("hour", "час"),
            ("minute", "минута"),
            ("second", "секунда"),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for pack in PACKS:
        if conn.execute(
            sa.text("SELECT id FROM packs WHERE slug = :slug"), {"slug": pack["slug"]}
        ).first():
            continue  # already seeded

        word_ids: list[int] = []
        for entry in pack["words"]:
            english, translation = entry[0], entry[1]
            example = entry[2] if len(entry) > 2 else None
            normalized = english.strip().lower()
            existing = conn.execute(
                sa.text(
                    "SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"
                ),
                {"n": normalized},
            ).first()
            if existing:
                word_ids.append(existing[0])
                continue
            row = conn.execute(
                sa.text(
                    "INSERT INTO words (track, writing, normalized_word, translation, example_sentence) "
                    "VALUES ('en', :w, :n, :t, :e) RETURNING id"
                ),
                {"w": english, "n": normalized, "t": translation, "e": example},
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
            "DELETE FROM pack_words WHERE pack_id IN "
            "(SELECT id FROM packs WHERE slug IN :slugs)"
        ).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": slugs},
    )
    conn.execute(
        sa.text("DELETE FROM packs WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", expanding=True)
        ),
        {"slugs": slugs},
    )
