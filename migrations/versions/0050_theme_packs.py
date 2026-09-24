"""Rebuild the thematic collections against a published syllabus.

The old themes were invented: 22 packs of exactly 20 words each, with weather
fused into nature, sport fused into hobbies, and transport duplicating travel.
Ten topics that every beginner syllabus opens with — daily routine, numbers,
appearance, shopping, services, everyday objects, countries, hotel, character,
drinks — did not exist at all, while 533 catalogue words belonged to no pack.

The taxonomy now follows the Cambridge A2 Key topic list and the British
Council A1-A2 topics, and the order follows the one thing those sources agree
on: start with what a learner can say about themselves today, then move
outward. That order lives in `app.domain.themes`; a theme holds until it is
finished rather than rotating daily, because switching every morning completes
nothing.

Three deliberate departures from the obvious design:

  * sizes are uneven on purpose, 12 to 70. An earlier plan targeted a flat 40
    per theme; measuring showed that would have meant inventing filler, since
    `colors` is complete at 16 and padding it means teaching turquoise — the
    exact failure this rework exists to end. A theme is done when it covers its
    situation, not when it hits a number.
  * closed sets carry their own order. Sorting numbers by corpus frequency
    produced «one, first, number, half, amount, count, eight, eighteen, eighty»
    — alphabetical noise dressed as a curriculum. `pack_words.position` keeps
    the declared order, so numbers are served one, two, three.
  * a word may belong to several themes. `price` is honestly both money and
    shopping, and the one-word-one-theme rule was what made themes look empty:
    of 496 core words, 124 existed already but sat filed under a neighbour.

Old packs are deactivated rather than dropped — users hold progress on words
that came from them, and `is_active` is reversible where a delete is not.

Revision ID: 0050
Revises: 0049
"""

from __future__ import annotations

from typing import NamedTuple

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

CATEGORY = "Темы"


class Pack(NamedTuple):
    slug: str
    title: str
    description: str
    words: tuple[str, ...]


PACKS: tuple[Pack, ...] = (
    Pack(
        "topic_numbers", "🔢 Числа",
        "числительные, счёт, количество",
        (
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety", "hundred", "thousand", "zero", "first", "third", "half",
        "quarter", "number", "count", "amount", "figure", "percent",
        ),
    ),
    Pack(
        "topic_colors", "🎨 Цвета",
        "цвета и оттенки",
        (
        "black", "blue", "bright", "brown", "color", "gold", "green", "grey", "orange",
        "pink", "purple", "red", "silver", "vivid", "white", "yellow",
        ),
    ),
    Pack(
        "topic_time", "🕐 Время и дни",
        "часы, дни недели, месяцы, времена года, слова о времени",
        (
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december", "spring", "summer", "autumn",
        "winter", "second", "minute", "hour", "day", "week", "month", "year", "morning",
        "afternoon", "evening", "night", "today", "tomorrow", "yesterday", "ago", "annual",
        "birthday", "century", "clock", "current", "daily", "date", "decade", "delay",
        "early", "future", "holiday", "last", "late", "later", "moment", "next", "noon",
        "now", "once", "past", "period", "previous", "prior", "recent", "recently",
        "schedule", "season", "soon", "time", "tonight", "weekend",
        ),
    ),
    Pack(
        "topic_family", "👪 Семья и люди",
        "родственники, друзья, слова о людях и отношениях",
        (
        "adopt", "adult", "aunt", "baby", "boy", "boyfriend", "brother", "child", "children",
        "cousin", "dad", "daughter", "family", "father", "female", "friend", "girl",
        "girlfriend", "grandfather", "grandmother", "guy", "hug", "human", "husband", "kid",
        "kiss", "lady", "male", "man", "marry", "mother", "neighbor", "parent", "partner",
        "people", "person", "relation", "relationship", "relative", "sister", "son", "uncle",
        "wife", "woman",
        ),
    ),
    Pack(
        "topic_appearance", "🙂 Внешность",
        "рост, телосложение, волосы, как человек выглядит",
        (
        "beautiful", "blonde", "cute", "dark", "face", "fair", "fat", "hair", "handsome",
        "high", "old", "pretty", "short", "slim", "strong", "style", "tall", "ugly", "weak",
        "young",
        ),
    ),
    Pack(
        "topic_body", "🫀 Тело",
        "части тела, органы, физические действия тела",
        (
        "arm", "ass", "back", "bite", "blink", "blood", "blush", "body", "brain", "breath",
        "breathe", "cheek", "chest", "chew", "ear", "eye", "eyebrow", "face", "feet",
        "finger", "foot", "frown", "gasp", "gaze", "glance", "glare", "groan", "hair",
        "hand", "head", "hear", "heart", "knee", "leg", "lip", "mouth", "neck", "nod",
        "nose", "rub", "shoulder", "sit", "skin", "stand", "stomach", "tooth", "touch",
        "voice", "wave",
        ),
    ),
    Pack(
        "topic_character", "🧠 Характер",
        "черты личности, поведение, какой человек",
        (
        "ambition", "argue", "bad", "behave", "brave", "busy", "calm", "capable", "careful",
        "character", "clever", "confident", "cool", "crazy", "credible", "curious",
        "dominate", "fight", "flexible", "friendly", "funny", "generous", "gentle", "happy",
        "hardworking", "honest", "honesty", "jealous", "kind", "lazy", "lonely", "lucky",
        "mad", "nice", "patience", "polite", "quiet", "reliable", "respect", "responsible",
        "rude", "sad", "serious", "shy", "smart", "strict", "stupid", "trait", "trust",
        ),
    ),
    Pack(
        "topic_routine", "☀️ Распорядок дня",
        "просыпаться, умываться, завтракать, ложиться спать",
        (
        "asleep", "breakfast", "brush", "dinner", "dress", "eat", "get", "go", "home",
        "lunch", "sleep", "soap", "study", "sweep", "wake", "walk", "wash", "wipe", "work",
        ),
    ),
    Pack(
        "topic_home", "🏠 Дом",
        "комнаты, мебель, части дома",
        (
        "apartment", "bathroom", "bed", "bedroom", "blanket", "carpet", "ceiling", "chair",
        "corner", "couch", "curtain", "desk", "door", "drawer", "fence", "floor",
        "furniture", "hall", "hallway", "handle", "hang", "home", "house", "kitchen", "lamp",
        "lock", "mirror", "roof", "room", "sheet", "shelf", "sofa", "stairs", "table",
        "wall", "window", "yard",
        ),
    ),
    Pack(
        "topic_objects", "🧷 Повседневные вещи",
        "предметы, которыми пользуются каждый день",
        (
        "bag", "bell", "book", "box", "brush", "card", "computer", "folder", "glass",
        "glasses", "gun", "iron", "key", "lamp", "money", "note", "object", "page", "paper",
        "pen", "pencil", "phone", "plastic", "ring", "rope", "scale", "scissors", "seat",
        "stick", "stuff", "thing", "tool", "umbrella", "watch",
        ),
    ),
    Pack(
        "topic_food", "🍎 Еда",
        "продукты, блюда, фрукты, овощи",
        (
        "apple", "banana", "bitter", "bread", "breakfast", "butter", "cake", "cheese",
        "chicken", "delicious", "dinner", "eat", "egg", "feed", "fish", "food", "fresh",
        "fruit", "grape", "lunch", "meal", "meat", "onion", "pasta", "portion", "potato",
        "product", "rice", "salad", "salty", "soup", "sour", "spicy", "stake", "sugar",
        "supper", "sweet", "taste", "tomato", "vegetable",
        ),
    ),
    Pack(
        "topic_drinks", "☕ Напитки",
        "напитки и всё, что пьют",
        (
        "bottle", "coffee", "cup", "drink", "glass", "ice", "juice", "milk", "soda", "tea",
        "water", "wine",
        ),
    ),
    Pack(
        "topic_cooking", "🍳 Кухня и готовка",
        "посуда, приготовление, ресторан, заказ еды",
        (
        "add", "bake", "bill", "boil", "cook", "cup", "cut", "drink", "eat", "fork", "fry",
        "kitchen", "knife", "menu", "mix", "oil", "order", "plate", "pour", "prepare",
        "restaurant", "salt", "serve", "spoon",
        ),
    ),
    Pack(
        "topic_clothes", "👕 Одежда",
        "одежда, обувь, аксессуары, размеры",
        (
        "belt", "boots", "button", "clothes", "coat", "dress", "gloves", "hat", "jacket",
        "jeans", "pocket", "scarf", "shirt", "shoe", "shoes", "size", "skirt", "sleeve",
        "socks", "suit", "sweater", "t-shirt", "tie", "trousers", "wear",
        ),
    ),
    Pack(
        "topic_city", "🏙 Город",
        "улицы, здания, городские места",
        (
        "area", "authority", "bank", "bar", "block", "bridge", "building", "capital",
        "center", "church", "cinema", "city", "crossroads", "facility", "hospital", "hotel",
        "jail", "park", "police", "road", "school", "shop", "sidewalk", "signpost", "square",
        "station", "street", "supermarket", "town", "village",
        ),
    ),
    Pack(
        "topic_transport", "🚗 Транспорт",
        "виды транспорта, поездки по городу, дорога",
        (
        "bike", "bus", "car", "deliver", "drive", "fly", "plane", "platform", "ride", "road",
        "station", "subway", "taxi", "ticket", "traffic", "train", "travel", "walk",
        ),
    ),
    Pack(
        "topic_shopping", "🛒 Покупки",
        "магазины, покупка, цены, товары",
        (
        "bag", "buy", "cashier", "cheap", "clothes", "counter", "customer", "discount",
        "expensive", "food", "gift", "market", "money", "pay", "price", "receipt", "sale",
        "sell", "shop", "size", "store",
        ),
    ),
    Pack(
        "topic_money", "💰 Деньги",
        "деньги, оплата, банк, стоимость",
        (
        "account", "afford", "bank", "bill", "borrow", "budget", "card", "cash", "change",
        "charge", "cheap", "coin", "cost", "credit", "currency", "deal", "debt", "dollar",
        "earn", "economic", "economy", "exchange", "expense", "expensive", "export", "fare",
        "financial", "fund", "income", "invest", "investment", "lend", "loan", "loss",
        "money", "note", "owe", "pay", "pound", "price", "profit", "property", "rent",
        "revenue", "rich", "salary", "save", "spend", "stock", "tax", "trade", "wallet",
        "wealth", "withdraw", "worth", "yield",
        ),
    ),
    Pack(
        "topic_services", "🏤 Услуги",
        "почта, банк, парикмахерская, ремонт, обслуживание",
        (
        "address", "agency", "bank", "close", "fix", "hairdresser", "help", "letter",
        "office", "open", "parcel", "post", "register", "repair", "send", "service", "wait",
        ),
    ),
    Pack(
        "topic_work", "💼 Работа",
        "профессии, офис, карьера, рабочие действия",
        (
        "agent", "associate", "boss", "business", "busy", "candidate", "career", "client",
        "collaborate", "colleague", "company", "computer", "conference", "contract",
        "deadline", "department", "design", "desk", "director", "document", "email",
        "employ", "employee", "finish", "firm", "guard", "hire", "industry", "interview",
        "job", "leader", "ledger", "management", "manager", "meeting", "miner", "negotiate",
        "office", "officer", "operate", "operation", "phone", "produce", "production",
        "profession", "professional", "project", "promote", "promotion", "report",
        "represent", "resume", "salary", "shift", "staff", "stakeholder", "start", "task",
        "team", "work", "worker",
        ),
    ),
    Pack(
        "topic_education", "🎓 Учёба",
        "школа, университет, предметы, учебные действия",
        (
        "book", "chalkboard", "class", "classroom", "college", "course", "degree", "diploma",
        "education", "essay", "exam", "grade", "homework", "knowledge", "learn", "lecture",
        "lesson", "library", "notebook", "pen", "pupil", "read", "research", "school",
        "science", "semester", "sentence", "spell", "student", "study", "subject", "teach",
        "teacher", "test", "university", "write",
        ),
    ),
    Pack(
        "topic_weather", "🌦 Погода",
        "погода, осадки, температура",
        (
        "breeze", "cloud", "cloudy", "cold", "cool", "dry", "fog", "forecast", "freezing",
        "hot", "humid", "lightning", "mild", "rain", "rainbow", "rainy", "shine", "snow",
        "storm", "sun", "sunny", "temperature", "thunder", "warm", "weather", "wet", "wind",
        "windy",
        ),
    ),
    Pack(
        "topic_nature", "🌲 Природа",
        "ландшафт, растения, море, горы, экология",
        (
        "air", "beach", "branch", "cave", "coast", "environment", "field", "fire", "flower",
        "forest", "garden", "grass", "ground", "hill", "island", "lake", "land", "leaf",
        "moon", "mountain", "natural", "nature", "north", "ocean", "park", "peak", "plant",
        "plateau", "river", "rock", "root", "rose", "sand", "sea", "sky", "soil", "south",
        "star", "stone", "sun", "tree", "universe", "valley", "west", "wood",
        ),
    ),
    Pack(
        "topic_animals", "🐘 Животные",
        "животные, птицы, насекомые, рыбы",
        (
        "animal", "bear", "bird", "cat", "cow", "dog", "duck", "elephant", "fish", "fly",
        "fox", "horse", "insect", "lion", "monkey", "mouse", "pet", "pig", "rabbit", "sheep",
        "snake", "spider", "tiger", "wild", "wolf",
        ),
    ),
    Pack(
        "topic_health", "🩺 Здоровье",
        "болезни, симптомы, врач, лекарства, самочувствие",
        (
        "appointment", "body", "cold", "cough", "disease", "doctor", "drug", "fever", "fit",
        "headache", "health", "healthy", "hospital", "hungry", "hurt", "ill", "illness",
        "injury", "medicine", "mental", "nurse", "pain", "patient", "pharmacy", "recover",
        "sick", "sneeze", "stomach", "suffer", "thirsty", "tired", "treatment", "weight",
        ),
    ),
    Pack(
        "topic_sport", "⚽ Спорт",
        "виды спорта, спортивные действия, соревнования",
        (
        "ball", "basketball", "climb", "coach", "compete", "competition", "exercise", "fit",
        "football", "game", "gym", "jump", "kick", "lose", "match", "play", "player", "race",
        "run", "score", "shoot", "sport", "swim", "swimming", "team", "tennis", "victory",
        "win",
        ),
    ),
    Pack(
        "topic_hobby", "🎯 Хобби",
        "увлечения, отдых, игры, рукоделие",
        (
        "celebrate", "chess", "club", "collect", "cook", "dance", "draw", "enjoy", "free",
        "fun", "game", "guitar", "hiking", "hobby", "interest", "joke", "knit", "music",
        "paint", "painting", "party", "photo", "play", "read", "relax", "rest", "sew",
        "sing", "time", "toy", "travel",
        ),
    ),
    Pack(
        "topic_media", "🎬 Развлечения и медиа",
        "кино, музыка, книги, телевидение, новости",
        (
        "art", "article", "author", "band", "book", "channel", "comment", "computer", "film",
        "internet", "listen", "magazine", "movie", "music", "news", "newspaper", "phone",
        "photo", "picture", "publish", "radio", "read", "record", "release", "review",
        "scenario", "show", "song", "stage", "story", "television", "watch",
        ),
    ),
    Pack(
        "topic_travel", "✈️ Путешествия",
        "аэропорт, билеты, багаж, поездка за границу",
        (
        "abroad", "airport", "arrival", "arrive", "bus", "customs", "depart", "departure",
        "flight", "gate", "hotel", "journey", "luggage", "map", "passport", "plane",
        "souvenir", "suitcase", "ticket", "tourist", "train", "travel", "trip", "vacation",
        "visit",
        ),
    ),
    Pack(
        "topic_hotel", "🏨 Отель",
        "гостиница, бронирование, номер",
        (
        "bed", "book", "breakfast", "check-in", "check-out", "guest", "hotel", "key",
        "night", "price", "reception", "reservation", "reserve", "room",
        ),
    ),
    Pack(
        "topic_countries", "🌍 Страны и языки",
        "страны, национальности, языки",
        (
        "chinese", "city", "country", "english", "foreign", "french", "german", "italian",
        "japanese", "language", "nation", "nationality", "russian", "spanish", "speak",
        "translate", "world",
        ),
    ),
    Pack(
        "topic_emotions", "😊 Эмоции",
        "чувства, настроение, эмоциональные состояния",
        (
        "admire", "afraid", "amaze", "anger", "angry", "annoy", "anxious", "attitude", "bad",
        "bore", "bored", "calm", "chuckle", "concern", "confused", "cry", "disappointed",
        "doubt", "embarrassed", "emotion", "excite", "excited", "fear", "feel", "giggle",
        "glad", "good", "grateful", "grin", "guilty", "happy", "hate", "hope", "horrible",
        "love", "mood", "nervous", "pleasure", "positive", "pride", "proud", "regret",
        "relieved", "sad", "satisfy", "scared", "shock", "smile", "sorry", "sure",
        "surprise", "surprised", "tear", "tired", "wish", "wonder", "worry",
        ),
    ),
    Pack(
        "topic_tech", "💻 Технологии",
        "компьютер, интернет, связь, устройства",
        (
        "access", "app", "application", "battery", "blockchain", "bug", "call", "charge",
        "charger", "click", "commit", "computer", "data", "device", "download", "email",
        "feature", "file", "generate", "internet", "keyboard", "laptop", "link", "machine",
        "mechanism", "message", "mouse", "network", "offline", "online", "password", "phone",
        "print", "program", "screen", "search", "site", "software", "technology",
        "telephone", "token", "update", "upload", "website", "wifi",
        ),
    ),)

# Hand-made packs this replaces. Deactivated, not deleted.
SUPERSEDED = (
    "theme_colors", "theme_family", "theme_body", "theme_food", "theme_time",
    "theme_travel", "theme_work", "theme_health", "theme_tech", "theme_money",
    "theme_emotions", "theme_weather", "theme_home", "theme_clothes",
    "theme_city", "theme_animals", "theme_education", "theme_sport",
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE packs SET is_active = false WHERE slug = ANY(:slugs)"),
        {"slugs": list(SUPERSEDED)},
    )
    for pack in PACKS:
        pack_id = bind.execute(
            sa.text(
                "INSERT INTO packs (slug, track, title, description, category,"
                " words_count, is_active)"
                " VALUES (:slug, 'en', :title, :descr, :cat, 0, true)"
                " ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title,"
                " description = EXCLUDED.description, is_active = true"
                " RETURNING id"
            ),
            {
                "slug": pack.slug,
                "title": pack.title,
                "descr": pack.description,
                "cat": CATEGORY,
            },
        ).scalar()
        # Rebuilt from scratch each run so re-applying cannot leave a stale
        # word behind in a pack whose contents changed.
        bind.execute(
            sa.text("DELETE FROM pack_words WHERE pack_id = :pid"), {"pid": pack_id}
        )
        bind.execute(
            sa.text(
                "INSERT INTO pack_words (pack_id, word_id, position)"
                " SELECT :pid, w.id, x.pos FROM unnest(CAST(:names AS text[]))"
                " WITH ORDINALITY AS x(name, pos)"
                " JOIN words w ON w.track = 'en' AND w.normalized_word = x.name"
                " ON CONFLICT DO NOTHING"
            ),
            {"pid": pack_id, "names": [w.lower() for w in pack.words]},
        )
        bind.execute(
            sa.text(
                "UPDATE packs SET words_count ="
                " (SELECT count(*) FROM pack_words WHERE pack_id = :pid)"
                " WHERE id = :pid"
            ),
            {"pid": pack_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM packs WHERE slug = ANY(:slugs)"),
        {"slugs": [p.slug for p in PACKS]},
    )
    bind.execute(
        sa.text("UPDATE packs SET is_active = true WHERE slug = ANY(:slugs)"),
        {"slugs": list(SUPERSEDED)},
    )
