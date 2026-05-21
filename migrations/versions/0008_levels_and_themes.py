"""frequency levels (A1/A2/B1) + more theme packs; re-group old seed packs

Revision ID: 0008
Revises: 0007
Create Date: 2025-01-10

Curated, frequency-ordered level packs (Уровни) + more themes (Темы).
Old single-topic seed packs are re-categorised under «Темы» so the browser
groups cleanly. Idempotent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Old seed-pack slugs to fold into the «Темы» group.
_OLD_THEME_SLUGS = ["crypto_basics", "it_starter", "business_basic", "travel_essentials", "basic_english_verbs"]

PACKS: list[dict] = [
    {
        "slug": "level_a1",
        "title": "🟢 Новичок (A1)",
        "description": "Самые частотные слова — фундамент. Учить первыми.",
        "category": "Уровни",
        "words": [
            ("be", "быть"), ("have", "иметь"), ("do", "делать"), ("go", "идти / ехать"),
            ("get", "получать"), ("make", "делать / создавать"), ("know", "знать"),
            ("think", "думать"), ("take", "брать"), ("see", "видеть"), ("come", "приходить"),
            ("want", "хотеть"), ("use", "использовать"), ("find", "находить"), ("give", "давать"),
            ("tell", "говорить / рассказывать"), ("work", "работать"), ("call", "звонить"),
            ("try", "пытаться"), ("ask", "спрашивать"), ("need", "нуждаться"), ("feel", "чувствовать"),
            ("leave", "уходить / оставлять"), ("put", "класть"), ("keep", "держать / хранить"),
            ("let", "позволять"), ("begin", "начинать"), ("help", "помогать"), ("show", "показывать"),
            ("hear", "слышать"), ("play", "играть"), ("run", "бежать"), ("move", "двигаться"),
            ("like", "нравиться"), ("live", "жить"), ("write", "писать"), ("sit", "сидеть"),
            ("stand", "стоять"), ("pay", "платить"), ("meet", "встречать"), ("learn", "учить"),
            ("read", "читать"), ("eat", "есть"), ("drink", "пить"), ("open", "открывать"),
            ("walk", "идти пешком"), ("buy", "покупать"), ("wait", "ждать"), ("love", "любить"),
            ("sleep", "спать"), ("time", "время"), ("day", "день"), ("year", "год"),
            ("people", "люди"), ("man", "мужчина"), ("woman", "женщина"), ("child", "ребёнок"),
            ("friend", "друг"), ("home", "дом"), ("water", "вода"), ("food", "еда"),
            ("good", "хороший"), ("bad", "плохой"), ("big", "большой"), ("small", "маленький"),
            ("new", "новый"), ("old", "старый"), ("happy", "счастливый"), ("now", "сейчас"),
            ("here", "здесь"), ("today", "сегодня"),
        ],
    },
    {
        "slug": "level_a2",
        "title": "🟡 Элементарный (A2)",
        "description": "Следующий слой частотных слов.",
        "category": "Уровни",
        "words": [
            ("decide", "решать"), ("explain", "объяснять"), ("describe", "описывать"),
            ("expect", "ожидать"), ("suggest", "предлагать"), ("agree", "соглашаться"),
            ("accept", "принимать"), ("improve", "улучшать"), ("increase", "увеличивать"),
            ("reduce", "уменьшать"), ("allow", "разрешать"), ("prefer", "предпочитать"),
            ("realize", "осознавать"), ("recognize", "узнавать"), ("prepare", "готовить"),
            ("manage", "справляться"), ("offer", "предлагать"), ("receive", "получать"),
            ("provide", "предоставлять"), ("require", "требовать"), ("avoid", "избегать"),
            ("consider", "рассматривать"), ("discover", "обнаруживать"), ("enjoy", "наслаждаться"),
            ("imagine", "представлять"), ("prevent", "предотвращать"), ("recommend", "рекомендовать"),
            ("solve", "решать (проблему)"), ("compare", "сравнивать"), ("continue", "продолжать"),
            ("control", "контролировать"), ("create", "создавать"), ("develop", "развивать"),
            ("introduce", "представлять (знакомить)"), ("notice", "замечать"), ("protect", "защищать"),
            ("refuse", "отказываться"), ("repeat", "повторять"), ("support", "поддерживать"),
            ("travel", "путешествовать"), ("difficult", "трудный"), ("easy", "лёгкий"),
            ("important", "важный"), ("possible", "возможный"), ("different", "разный"),
            ("similar", "похожий"), ("expensive", "дорогой"), ("cheap", "дешёвый"),
            ("dangerous", "опасный"), ("comfortable", "удобный"),
        ],
    },
    {
        "slug": "level_b1",
        "title": "🟠 Средний (B1)",
        "description": "Слова уровня B1 — для уверенной речи.",
        "category": "Уровни",
        "words": [
            ("admit", "признавать"), ("announce", "объявлять"), ("apologize", "извиняться"),
            ("argue", "спорить"), ("complain", "жаловаться"), ("confirm", "подтверждать"),
            ("encourage", "поощрять"), ("establish", "устанавливать"), ("examine", "изучать"),
            ("identify", "определять"), ("influence", "влиять"), ("maintain", "поддерживать"),
            ("observe", "наблюдать"), ("participate", "участвовать"), ("perform", "выполнять"),
            ("persuade", "убеждать"), ("predict", "предсказывать"), ("react", "реагировать"),
            ("replace", "заменять"), ("represent", "представлять"), ("respond", "отвечать"),
            ("reveal", "раскрывать"), ("struggle", "бороться"), ("survive", "выживать"),
            ("achieve", "достигать"), ("behaviour", "поведение"), ("decision", "решение"),
            ("development", "развитие"), ("environment", "окружающая среда"), ("experience", "опыт"),
            ("knowledge", "знание"), ("opportunity", "возможность"), ("relationship", "отношения"),
            ("responsibility", "ответственность"), ("situation", "ситуация"), ("society", "общество"),
            ("solution", "решение"), ("success", "успех"), ("accurate", "точный"),
            ("aware", "осведомлённый"), ("capable", "способный"), ("complex", "сложный"),
            ("confident", "уверенный"), ("efficient", "эффективный"), ("essential", "необходимый"),
            ("obvious", "очевидный"), ("relevant", "уместный"), ("reliable", "надёжный"),
            ("significant", "значительный"),
        ],
    },
    {
        "slug": "theme_travel",
        "title": "Путешествия",
        "description": "Слова для поездок и аэропорта.",
        "category": "Темы",
        "words": [
            ("airport", "аэропорт"), ("flight", "рейс"), ("ticket", "билет"), ("passport", "паспорт"),
            ("luggage", "багаж"), ("suitcase", "чемодан"), ("gate", "выход на посадку"),
            ("departure", "вылет"), ("arrival", "прилёт"), ("customs", "таможня"),
            ("boarding", "посадка"), ("delay", "задержка"), ("hotel", "отель"),
            ("reservation", "бронь"), ("map", "карта"), ("trip", "поездка"), ("journey", "путешествие"),
            ("abroad", "за границей"), ("tourist", "турист"), ("souvenir", "сувенир"),
        ],
    },
    {
        "slug": "theme_work",
        "title": "Работа и офис",
        "description": "Слова про работу.",
        "category": "Темы",
        "words": [
            ("office", "офис"), ("manager", "менеджер"), ("employee", "сотрудник"),
            ("colleague", "коллега"), ("meeting", "встреча"), ("deadline", "дедлайн"),
            ("salary", "зарплата"), ("contract", "контракт"), ("interview", "собеседование"),
            ("resume", "резюме"), ("task", "задача"), ("project", "проект"), ("report", "отчёт"),
            ("schedule", "расписание"), ("client", "клиент"), ("boss", "начальник"),
            ("team", "команда"), ("promotion", "повышение"), ("skill", "навык"), ("hire", "нанимать"),
        ],
    },
    {
        "slug": "theme_health",
        "title": "Здоровье",
        "description": "Слова о здоровье и врачах.",
        "category": "Темы",
        "words": [
            ("health", "здоровье"), ("doctor", "врач"), ("nurse", "медсестра"),
            ("hospital", "больница"), ("medicine", "лекарство"), ("pain", "боль"),
            ("illness", "болезнь"), ("disease", "заболевание"), ("fever", "жар"),
            ("cough", "кашель"), ("headache", "головная боль"), ("injury", "травма"),
            ("treatment", "лечение"), ("recover", "выздоравливать"), ("healthy", "здоровый"),
            ("sick", "больной"), ("pharmacy", "аптека"), ("patient", "пациент"),
            ("blood", "кровь"), ("breath", "дыхание"),
        ],
    },
    {
        "slug": "theme_tech",
        "title": "Технологии",
        "description": "Компьютеры и интернет.",
        "category": "Темы",
        "words": [
            ("computer", "компьютер"), ("laptop", "ноутбук"), ("phone", "телефон"),
            ("screen", "экран"), ("keyboard", "клавиатура"), ("mouse", "мышь"),
            ("internet", "интернет"), ("website", "сайт"), ("password", "пароль"),
            ("file", "файл"), ("folder", "папка"), ("download", "скачивать"),
            ("upload", "загружать"), ("software", "программа"), ("app", "приложение"),
            ("update", "обновление"), ("device", "устройство"), ("battery", "батарея"),
            ("charger", "зарядка"), ("network", "сеть"),
        ],
    },
    {
        "slug": "theme_money",
        "title": "Деньги",
        "description": "Финансы и покупки.",
        "category": "Темы",
        "words": [
            ("money", "деньги"), ("cash", "наличные"), ("bank", "банк"), ("account", "счёт"),
            ("budget", "бюджет"), ("price", "цена"), ("cost", "стоимость"), ("discount", "скидка"),
            ("debt", "долг"), ("loan", "кредит"), ("invest", "вкладывать"), ("save", "копить"),
            ("spend", "тратить"), ("earn", "зарабатывать"), ("bill", "счёт (к оплате)"),
            ("tax", "налог"), ("profit", "прибыль"), ("income", "доход"), ("expense", "расход"),
            ("rich", "богатый"),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    # Re-group old single-topic seed packs under «Темы».
    conn.execute(
        sa.text("UPDATE packs SET category = 'Темы' WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", expanding=True)
        ),
        {"slugs": _OLD_THEME_SLUGS},
    )

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
    # Restore old packs' categories.
    restore = {
        "crypto_basics": "Crypto", "it_starter": "IT", "business_basic": "Business",
        "travel_essentials": "Travel", "basic_english_verbs": "Basic English",
    }
    for slug, cat in restore.items():
        conn.execute(
            sa.text("UPDATE packs SET category = :c WHERE slug = :s"), {"c": cat, "s": slug}
        )
