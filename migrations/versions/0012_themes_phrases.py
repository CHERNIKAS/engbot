"""more theme packs + situational phrase packs

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-21

Adds 8 new theme packs (emotions, weather, home, clothes, city, animals,
education, sport) and 5 situational phrase packs (hotel, doctor, shopping,
directions, phone). Idempotent: words upserted by (track, normalized),
pack_words ON CONFLICT DO NOTHING, words_count = len.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

PACKS: list[dict] = [
    {
        "slug": "theme_emotions",
        "title": "Эмоции и чувства",
        "description": "Как описать настроение и состояние.",
        "category": "Темы",
        "words": [
            ("happy", "счастливый"), ("sad", "грустный"), ("angry", "злой"),
            ("afraid", "испуганный"), ("excited", "взволнованный (радостно)"),
            ("bored", "скучающий"), ("proud", "гордый"), ("jealous", "ревнивый / завистливый"),
            ("nervous", "нервный"), ("calm", "спокойный"), ("surprised", "удивлённый"),
            ("confused", "растерянный"), ("lonely", "одинокий"), ("grateful", "благодарный"),
            ("anxious", "тревожный"), ("embarrassed", "смущённый"),
            ("disappointed", "разочарованный"), ("relieved", "почувствовавший облегчение"),
            ("curious", "любопытный"), ("confident", "уверенный"),
        ],
    },
    {
        "slug": "theme_weather",
        "title": "Погода и природа",
        "description": "Слова о погоде и временах года.",
        "category": "Темы",
        "words": [
            ("weather", "погода"), ("rain", "дождь"), ("snow", "снег"), ("sun", "солнце"),
            ("cloud", "облако"), ("wind", "ветер"), ("storm", "буря / шторм"), ("fog", "туман"),
            ("thunder", "гром"), ("lightning", "молния"), ("rainbow", "радуга"),
            ("temperature", "температура"), ("forecast", "прогноз"), ("humid", "влажный"),
            ("freezing", "морозный / очень холодный"), ("sunny", "солнечный"),
            ("cloudy", "облачный"), ("windy", "ветреный"), ("mild", "мягкий (о погоде)"),
            ("breeze", "лёгкий ветерок"),
        ],
    },
    {
        "slug": "theme_home",
        "title": "Дом и интерьер",
        "description": "Комнаты, мебель и вещи дома.",
        "category": "Темы",
        "words": [
            ("kitchen", "кухня"), ("bathroom", "ванная"), ("bedroom", "спальня"),
            ("furniture", "мебель"), ("table", "стол"), ("chair", "стул"), ("bed", "кровать"),
            ("sofa", "диван"), ("lamp", "лампа"), ("mirror", "зеркало"), ("shelf", "полка"),
            ("drawer", "выдвижной ящик"), ("curtain", "штора"), ("carpet", "ковёр"),
            ("ceiling", "потолок"), ("floor", "пол"), ("wall", "стена"), ("stairs", "лестница"),
            ("window", "окно"), ("blanket", "одеяло"),
        ],
    },
    {
        "slug": "theme_clothes",
        "title": "Одежда",
        "description": "Одежда и аксессуары.",
        "category": "Темы",
        "words": [
            ("shirt", "рубашка"), ("trousers", "брюки"), ("dress", "платье"), ("skirt", "юбка"),
            ("jacket", "куртка / пиджак"), ("coat", "пальто"), ("shoes", "туфли / обувь"),
            ("socks", "носки"), ("hat", "шляпа / шапка"), ("gloves", "перчатки"),
            ("scarf", "шарф"), ("belt", "ремень"), ("jeans", "джинсы"), ("sweater", "свитер"),
            ("suit", "костюм"), ("tie", "галстук"), ("boots", "ботинки / сапоги"),
            ("pocket", "карман"), ("button", "пуговица"), ("sleeve", "рукав"),
        ],
    },
    {
        "slug": "theme_city",
        "title": "Город и транспорт",
        "description": "Улицы, транспорт и навигация.",
        "category": "Темы",
        "words": [
            ("street", "улица"), ("road", "дорога"), ("bridge", "мост"), ("building", "здание"),
            ("station", "станция / вокзал"), ("bus", "автобус"), ("train", "поезд"),
            ("subway", "метро"), ("taxi", "такси"), ("traffic", "движение / пробки"),
            ("sidewalk", "тротуар"), ("crossroads", "перекрёсток"), ("square", "площадь"),
            ("park", "парк"), ("map", "карта"), ("ticket", "билет"), ("platform", "платформа"),
            ("fare", "плата за проезд"), ("corner", "угол"), ("signpost", "указатель"),
        ],
    },
    {
        "slug": "theme_animals",
        "title": "Животные",
        "description": "Домашние и дикие животные.",
        "category": "Темы",
        "words": [
            ("dog", "собака"), ("cat", "кошка"), ("bird", "птица"), ("fish", "рыба"),
            ("horse", "лошадь"), ("cow", "корова"), ("sheep", "овца"), ("pig", "свинья"),
            ("chicken", "курица"), ("rabbit", "кролик"), ("lion", "лев"), ("tiger", "тигр"),
            ("bear", "медведь"), ("elephant", "слон"), ("monkey", "обезьяна"), ("snake", "змея"),
            ("wolf", "волк"), ("fox", "лиса"), ("mouse", "мышь"), ("duck", "утка"),
        ],
    },
    {
        "slug": "theme_education",
        "title": "Образование",
        "description": "Учёба, школа и университет.",
        "category": "Темы",
        "words": [
            ("student", "студент / ученик"), ("teacher", "учитель"), ("lesson", "урок"),
            ("homework", "домашнее задание"), ("exam", "экзамен"), ("grade", "оценка / класс"),
            ("subject", "предмет"), ("classroom", "класс (комната)"), ("university", "университет"),
            ("degree", "учёная степень"), ("library", "библиотека"), ("knowledge", "знание"),
            ("notebook", "тетрадь"), ("pencil", "карандаш"), ("semester", "семестр"),
            ("lecture", "лекция"), ("essay", "эссе / сочинение"), ("diploma", "диплом"),
            ("pupil", "ученик"), ("chalkboard", "школьная доска"),
        ],
    },
    {
        "slug": "theme_sport",
        "title": "Спорт и хобби",
        "description": "Спорт, игры и увлечения.",
        "category": "Темы",
        "words": [
            ("sport", "спорт"), ("football", "футбол"), ("basketball", "баскетбол"),
            ("tennis", "теннис"), ("swimming", "плавание"), ("running", "бег"),
            ("cycling", "велоспорт"), ("gym", "спортзал"), ("team", "команда"),
            ("coach", "тренер"), ("match", "матч"), ("score", "счёт"), ("hobby", "хобби"),
            ("painting", "рисование / живопись"), ("dancing", "танцы"), ("fishing", "рыбалка"),
            ("hiking", "пеший туризм"), ("camping", "кемпинг"), ("chess", "шахматы"),
            ("guitar", "гитара"),
        ],
    },
    {
        "slug": "phrases_hotel",
        "title": "В отеле",
        "description": "Фразы для заселения и проживания.",
        "category": "Фразы",
        "words": [
            ("I have a booking", "У меня бронь"),
            ("Do you have any rooms?", "У вас есть свободные номера?"),
            ("I'd like a double room", "Я хотел бы двухместный номер"),
            ("What time is check-out?", "Во сколько выезд?"),
            ("Is breakfast included?", "Завтрак включён?"),
            ("Can I have the key?", "Можно ключ?"),
            ("The room is too cold", "В номере слишком холодно"),
            ("The Wi-Fi isn't working", "Wi-Fi не работает"),
            ("Can I leave my luggage here?", "Можно оставить багаж здесь?"),
            ("Where is the elevator?", "Где лифт?"),
            ("I'd like to check out", "Я хочу выехать"),
            ("Could I get a wake-up call?", "Можно разбудить меня звонком?"),
        ],
    },
    {
        "slug": "phrases_doctor",
        "title": "У врача",
        "description": "Фразы для аптеки и приёма у врача.",
        "category": "Фразы",
        "words": [
            ("I don't feel well", "Мне нехорошо"),
            ("I have a headache", "У меня болит голова"),
            ("I have a fever", "У меня температура"),
            ("It hurts here", "Здесь болит"),
            ("I need a doctor", "Мне нужен врач"),
            ("I'm allergic to penicillin", "У меня аллергия на пенициллин"),
            ("Can you call an ambulance?", "Можете вызвать скорую?"),
            ("I have a sore throat", "У меня болит горло"),
            ("How often should I take this?", "Как часто это принимать?"),
            ("I feel dizzy", "У меня кружится голова"),
            ("I've caught a cold", "Я простудился"),
            ("Where is the nearest pharmacy?", "Где ближайшая аптека?"),
        ],
    },
    {
        "slug": "phrases_shopping",
        "title": "Покупки",
        "description": "Фразы для магазина.",
        "category": "Фразы",
        "words": [
            ("How much does it cost?", "Сколько это стоит?"),
            ("Do you have this in another size?", "Есть это в другом размере?"),
            ("Can I try it on?", "Можно примерить?"),
            ("I'm just looking", "Я просто смотрю"),
            ("Do you take cards?", "Вы принимаете карты?"),
            ("It's too expensive", "Это слишком дорого"),
            ("Can I get a discount?", "Можно скидку?"),
            ("Where is the fitting room?", "Где примерочная?"),
            ("I'll take it", "Я возьму это"),
            ("Can I have a receipt?", "Можно чек?"),
            ("Is it on sale?", "На это есть скидка?"),
            ("Do you have a smaller one?", "Есть поменьше?"),
        ],
    },
    {
        "slug": "phrases_directions",
        "title": "Как пройти",
        "description": "Спросить и понять дорогу.",
        "category": "Фразы",
        "words": [
            ("How do I get to...?", "Как добраться до...?"),
            ("Is it far from here?", "Это далеко отсюда?"),
            ("Where is the nearest metro?", "Где ближайшее метро?"),
            ("Go straight ahead", "Идите прямо"),
            ("Turn left at the corner", "Поверните налево на углу"),
            ("It's next to the bank", "Это рядом с банком"),
            ("It's across the street", "Это через дорогу"),
            ("Can you show me on the map?", "Покажете на карте?"),
            ("How long does it take?", "Сколько времени это займёт?"),
            ("I think I'm lost", "Кажется, я заблудился"),
            ("Is this the right way?", "Это правильная дорога?"),
            ("It's around the corner", "Это за углом"),
        ],
    },
    {
        "slug": "phrases_phone",
        "title": "Телефон и звонки",
        "description": "Фразы для телефонного разговора.",
        "category": "Фразы",
        "words": [
            ("Who's calling?", "Кто звонит?"),
            ("Can I speak to...?", "Можно поговорить с...?"),
            ("Hold on, please", "Подождите, пожалуйста"),
            ("He's not available right now", "Его сейчас нет / он недоступен"),
            ("Can I leave a message?", "Можно оставить сообщение?"),
            ("Could you call me back?", "Можете перезвонить?"),
            ("The line is busy", "Линия занята"),
            ("You've got the wrong number", "Вы ошиблись номером"),
            ("I can't hear you well", "Я плохо вас слышу"),
            ("Let me call you back", "Я перезвоню вам"),
            ("My battery is dying", "У меня садится телефон"),
            ("Can you speak up?", "Можете говорить громче?"),
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
    for pack in PACKS:
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
    slugs = [p["slug"] for p in PACKS]
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
