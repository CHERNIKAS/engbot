"""expand frequency levels (A1/A2/B1) + add B2

Revision ID: 0010
Revises: 0009
Create Date: 2025-01-14

Appends more curated words to the existing level packs and adds 🔴 Выше
среднего (B2). Idempotent: words upserted by (track, normalized), pack_words
ON CONFLICT DO NOTHING, words_count recomputed from pack_words.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# Extra words appended to existing level packs (distinct from each other + 0008).
EXPANSIONS: dict[str, list[tuple[str, str]]] = {
    "level_a1": [
        ("name", "имя"), ("family", "семья"), ("house", "дом (здание)"), ("school", "школа"),
        ("city", "город"), ("car", "машина"), ("book", "книга"), ("word", "слово"),
        ("night", "ночь"), ("morning", "утро"), ("week", "неделя"), ("month", "месяц"),
        ("hour", "час"), ("door", "дверь"), ("room", "комната"), ("place", "место"),
        ("number", "число"), ("question", "вопрос"), ("answer", "ответ"), ("speak", "говорить"),
        ("stop", "останавливать"), ("start", "начинать"), ("turn", "поворачивать"),
        ("bring", "приносить"), ("hold", "держать"), ("send", "отправлять"), ("spend", "тратить"),
        ("lose", "терять"), ("win", "выигрывать"), ("wear", "носить (одежду)"), ("break", "ломать"),
        ("grow", "расти"), ("catch", "ловить"), ("teach", "учить (других)"), ("fly", "летать"),
        ("drive", "водить"), ("choose", "выбирать"), ("cook", "готовить (еду)"), ("wash", "мыть"),
        ("close", "закрывать"), ("hot", "горячий"), ("cold", "холодный"), ("warm", "тёплый"),
        ("fast", "быстрый"), ("slow", "медленный"), ("hard", "трудный / твёрдый"),
        ("long", "длинный"), ("short", "короткий"), ("high", "высокий"), ("low", "низкий"),
        ("right", "правильный / правый"), ("wrong", "неправильный"), ("early", "ранний"),
        ("late", "поздний"), ("nice", "милый / приятный"), ("beautiful", "красивый"),
        ("strong", "сильный"), ("weak", "слабый"), ("ready", "готовый"), ("sure", "уверенный"),
    ],
    "level_a2": [
        ("arrive", "прибывать"), ("affect", "влиять на"), ("appreciate", "ценить"),
        ("arrange", "устраивать"), ("attend", "посещать"), ("attract", "привлекать"),
        ("blame", "винить"), ("borrow", "брать в долг"), ("celebrate", "праздновать"),
        ("complete", "завершать"), ("connect", "соединять"), ("contain", "содержать"),
        ("deliver", "доставлять"), ("deny", "отрицать"), ("design", "проектировать"),
        ("disappear", "исчезать"), ("discuss", "обсуждать"), ("divide", "делить"),
        ("escape", "убегать"), ("exist", "существовать"), ("explore", "исследовать"),
        ("express", "выражать"), ("fix", "чинить"), ("hate", "ненавидеть"), ("hope", "надеяться"),
        ("hurry", "спешить"), ("invite", "приглашать"), ("join", "присоединяться"),
        ("lend", "одалживать"), ("matter", "иметь значение"), ("measure", "измерять"),
        ("mix", "смешивать"), ("order", "заказывать"), ("owe", "быть должным"),
        ("paint", "красить / рисовать"), ("press", "нажимать"), ("pull", "тянуть"),
        ("push", "толкать"), ("relax", "расслабляться"), ("rely", "полагаться"),
        ("rent", "арендовать"), ("repair", "ремонтировать"), ("rescue", "спасать"),
        ("respect", "уважать"), ("share", "делиться"), ("shout", "кричать"), ("sign", "подписывать"),
        ("steal", "красть"), ("succeed", "преуспевать"), ("surprise", "удивлять"),
        ("touch", "трогать"), ("trust", "доверять"), ("waste", "тратить впустую"),
        ("wonder", "интересоваться / удивляться"), ("seem", "казаться"),
    ],
    "level_b1": [
        ("advantage", "преимущество"), ("attempt", "попытка"), ("benefit", "выгода"),
        ("challenge", "вызов"), ("conclusion", "вывод"), ("consequence", "последствие"),
        ("difference", "различие"), ("effect", "эффект"), ("effort", "усилие"),
        ("evidence", "доказательство"), ("factor", "фактор"), ("feature", "особенность"),
        ("function", "функция"), ("goal", "цель"), ("impact", "воздействие"),
        ("issue", "вопрос / проблема"), ("method", "метод"), ("opinion", "мнение"),
        ("process", "процесс"), ("progress", "прогресс"), ("purpose", "цель / назначение"),
        ("quality", "качество"), ("range", "диапазон"), ("resource", "ресурс"), ("risk", "риск"),
        ("role", "роль"), ("source", "источник"), ("structure", "структура"), ("value", "ценность"),
        ("appropriate", "подходящий"), ("available", "доступный"), ("common", "распространённый"),
        ("constant", "постоянный"), ("current", "текущий"), ("flexible", "гибкий"),
        ("frequent", "частый"), ("major", "основной"), ("minor", "незначительный"),
        ("particular", "особенный"), ("previous", "предыдущий"), ("rare", "редкий"),
        ("recent", "недавний"), ("specific", "конкретный"), ("sudden", "внезапный"),
        ("typical", "типичный"), ("various", "различные"), ("assume", "предполагать"),
        ("define", "определять"), ("ensure", "обеспечивать"), ("estimate", "оценивать"),
        ("evaluate", "оценивать"), ("indicate", "указывать"), ("involve", "вовлекать"),
        ("occur", "происходить"), ("propose", "предлагать"), ("seek", "искать"),
    ],
}

NEW_PACKS: list[dict] = [
    {
        "slug": "level_b2",
        "title": "🔴 Выше среднего (B2)",
        "description": "Продвинутая и абстрактная лексика.",
        "category": "Уровни",
        "words": [
            ("acknowledge", "признавать"), ("adequate", "достаточный"), ("ambiguous", "неоднозначный"),
            ("anticipate", "предвидеть"), ("assess", "оценивать"), ("assert", "утверждать"),
            ("attribute", "приписывать"), ("bias", "предвзятость"), ("coherent", "связный"),
            ("comprehensive", "всесторонний"), ("compromise", "компромисс"),
            ("considerable", "значительный"), ("constrain", "ограничивать"),
            ("contradict", "противоречить"), ("controversial", "спорный"), ("convey", "передавать (смысл)"),
            ("deduce", "выводить (логически)"), ("deliberate", "намеренный"),
            ("derive", "получать / происходить"), ("deteriorate", "ухудшаться"),
            ("diminish", "уменьшать"), ("distinct", "отчётливый"), ("diverse", "разнообразный"),
            ("eliminate", "устранять"), ("emerge", "появляться"), ("encounter", "сталкиваться"),
            ("endure", "выдерживать"), ("enhance", "улучшать"), ("exceed", "превышать"),
            ("explicit", "явный"), ("exploit", "использовать"), ("facilitate", "способствовать"),
            ("feasible", "осуществимый"), ("fundamental", "фундаментальный"), ("hypothesis", "гипотеза"),
            ("implication", "последствие / подтекст"), ("implicit", "неявный"),
            ("inevitable", "неизбежный"), ("inherent", "присущий"), ("intervene", "вмешиваться"),
            ("justify", "оправдывать"), ("legitimate", "законный / обоснованный"),
            ("manipulate", "манипулировать"), ("notion", "понятие"), ("ongoing", "продолжающийся"),
            ("phenomenon", "явление"), ("plausible", "правдоподобный"), ("prevail", "преобладать"),
            ("profound", "глубокий"), ("prominent", "выдающийся"), ("rational", "рациональный"),
            ("reinforce", "укреплять"), ("scope", "масштаб / охват"), ("subsequent", "последующий"),
            ("subtle", "тонкий / неуловимый"), ("undermine", "подрывать"),
            ("underlying", "лежащий в основе"), ("viable", "жизнеспособный"),
            ("accumulate", "накапливать"), ("advocate", "выступать за"),
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

    for slug, words in EXPANSIONS.items():
        pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": slug}).first()
        if pack is None:
            continue
        pack_id = pack[0]
        pos = (
            conn.execute(
                sa.text("SELECT COALESCE(MAX(position), -1) FROM pack_words WHERE pack_id = :p"),
                {"p": pack_id},
            ).scalar()
            or -1
        )
        for english, translation in words:
            wid = _upsert_word(conn, english, translation)
            pos += 1
            conn.execute(
                sa.text(
                    "INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :pos) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"p": pack_id, "w": wid, "pos": pos},
            )
        conn.execute(
            sa.text(
                "UPDATE packs SET words_count = "
                "(SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"
            ),
            {"p": pack_id},
        )

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
    # Remove appended words from existing level packs, recompute counts.
    for slug, words in EXPANSIONS.items():
        pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": slug}).first()
        if pack is None:
            continue
        pack_id = pack[0]
        normalized = [en.strip().lower() for en, _ in words]
        conn.execute(
            sa.text(
                "DELETE FROM pack_words WHERE pack_id = :p AND word_id IN "
                "(SELECT id FROM words WHERE track = 'en' AND normalized_word IN :n)"
            ).bindparams(sa.bindparam("n", expanding=True)),
            {"p": pack_id, "n": normalized},
        )
        conn.execute(
            sa.text(
                "UPDATE packs SET words_count = "
                "(SELECT count(*) FROM pack_words WHERE pack_id = :p) WHERE id = :p"
            ),
            {"p": pack_id},
        )
    # Drop new packs.
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
