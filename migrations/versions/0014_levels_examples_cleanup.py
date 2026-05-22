"""grow levels (+examples) + rename legacy English-titled packs

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-22

Three things:
1. Rename the 5 legacy seed packs (English titles) to consistent RU titles.
2. Append 40 new words to each level (A1/A2/B1/B2), all verified distinct
   from the existing corpus, each WITH an example sentence so cards are richer.
Idempotent: words upserted by (track, normalized), pack_words ON CONFLICT
DO NOTHING, words_count recomputed from pack_words.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

# slug -> (new RU title, old EN title for downgrade)
RENAMES: dict[str, tuple[str, str]] = {
    "crypto_basics": ("Криптовалюты", "Crypto Basics"),
    "it_starter": ("IT и интернет", "IT Starter"),
    "business_basic": ("Бизнес", "Business Basics"),
    "travel_essentials": ("Путешествия: разговорник", "Travel Essentials"),
    "basic_english_verbs": ("Базовые глаголы", "Basic English Verbs"),
}

# slug -> list of (english, translation, example_sentence)
EXPANSIONS: dict[str, list[tuple[str, str, str]]] = {
    "level_a1": [
        ("bag", "сумка", "I put my books in the bag."),
        ("ball", "мяч", "The kids play with a ball."),
        ("box", "коробка", "There is a gift in the box."),
        ("cake", "торт", "She made a chocolate cake."),
        ("clean", "чистый / убирать", "Please clean your room."),
        ("clock", "часы (настенные)", "The clock on the wall is slow."),
        ("clothes", "одежда", "I need new clothes."),
        ("count", "считать", "Count to ten, please."),
        ("dance", "танцевать", "They dance every weekend."),
        ("dark", "тёмный", "It is dark outside."),
        ("dirty", "грязный", "My shoes are dirty."),
        ("dream", "мечта / сон", "I had a strange dream."),
        ("end", "конец / заканчиваться", "The film has a happy end."),
        ("enough", "достаточно", "We have enough time."),
        ("fall", "падать", "Leaves fall in autumn."),
        ("far", "далеко", "The shop is not far."),
        ("fill", "наполнять", "Fill the glass with water."),
        ("fire", "огонь", "We sat near the fire."),
        ("first", "первый", "This is my first day."),
        ("fun", "веселье", "We had a lot of fun."),
        ("game", "игра", "Let's play a game."),
        ("garden", "сад", "Flowers grow in the garden."),
        ("glass", "стакан / стекло", "I drank a glass of milk."),
        ("hello", "привет", "Hello, how are you?"),
        ("holiday", "отпуск / праздник", "We go on holiday in July."),
        ("idea", "идея", "That is a great idea."),
        ("job", "работа (место)", "She has a new job."),
        ("key", "ключ", "I lost my house key."),
        ("kind", "добрый / вид", "He is very kind to me."),
        ("last", "последний / длиться", "This is the last piece."),
        ("letter", "письмо / буква", "I wrote a letter to my friend."),
        ("light", "свет / лёгкий", "Turn on the light."),
        ("little", "маленький / мало", "We have little time."),
        ("music", "музыка", "I love this music."),
        ("page", "страница", "Open the book on page five."),
        ("party", "вечеринка", "We had a birthday party."),
        ("pen", "ручка", "Can I borrow your pen?"),
        ("picture", "картинка / фото", "She drew a nice picture."),
        ("problem", "проблема", "We have a small problem."),
        ("sky", "небо", "The sky is blue today."),
    ],
    "level_a2": [
        ("add", "добавлять", "Add some salt to the soup."),
        ("admire", "восхищаться", "I admire her courage."),
        ("afford", "позволить себе", "I can't afford a new car."),
        ("amazing", "удивительный", "The view was amazing."),
        ("annoy", "раздражать", "Loud noise annoys me."),
        ("apply", "подавать заявку / применять", "She applied for the job."),
        ("attach", "прикреплять", "Attach the file to the email."),
        ("average", "средний", "He is of average height."),
        ("behave", "вести себя", "The children behaved well."),
        ("belong", "принадлежать", "This book belongs to me."),
        ("brave", "храбрый", "It was a brave decision."),
        ("breathe", "дышать", "Breathe slowly and relax."),
        ("careful", "осторожный", "Be careful on the ice."),
        ("clever", "умный", "She is a clever student."),
        ("collect", "собирать (коллекцию)", "He collects old coins."),
        ("crowd", "толпа", "A big crowd gathered."),
        ("daily", "ежедневный", "Reading is my daily habit."),
        ("destroy", "разрушать", "The storm destroyed the house."),
        ("empty", "пустой", "The box is empty."),
        ("excellent", "отличный", "Your work is excellent."),
        ("expand", "расширять", "The company wants to expand."),
        ("famous", "знаменитый", "She is a famous singer."),
        ("foreign", "иностранный", "He speaks three foreign languages."),
        ("forgive", "прощать", "Please forgive me."),
        ("gather", "собираться", "We gathered in the hall."),
        ("generous", "щедрый", "He is generous with his time."),
        ("huge", "огромный", "They live in a huge house."),
        ("ignore", "игнорировать", "Don't ignore the warning."),
        ("include", "включать", "The price includes breakfast."),
        ("invent", "изобретать", "He invented a new device."),
        ("lazy", "ленивый", "I feel lazy on Sundays."),
        ("local", "местный", "We ate at a local cafe."),
        ("lucky", "удачливый", "You are very lucky."),
        ("modern", "современный", "She likes modern art."),
        ("polite", "вежливый", "He is always polite."),
        ("popular", "популярный", "This song is very popular."),
        ("pour", "наливать", "Pour me some tea, please."),
        ("prove", "доказывать", "Can you prove it?"),
        ("quiet", "тихий", "The library is quiet."),
        ("raise", "поднимать / повышать", "Raise your hand to answer."),
    ],
    "level_b1": [
        ("ability", "способность", "She has the ability to lead."),
        ("absorb", "поглощать", "Plants absorb sunlight."),
        ("accuse", "обвинять", "They accused him of lying."),
        ("adapt", "приспосабливаться", "Animals adapt to the cold."),
        ("adopt", "принимать / усыновлять", "The team adopted a new plan."),
        ("aim", "цель / стремиться", "Our aim is to win."),
        ("alternative", "альтернатива", "Is there an alternative?"),
        ("analysis", "анализ", "The analysis took two weeks."),
        ("annual", "ежегодный", "They hold an annual meeting."),
        ("apparent", "очевидный", "It became apparent he was right."),
        ("approve", "одобрять", "The boss approved the budget."),
        ("attitude", "отношение / настрой", "She has a positive attitude."),
        ("background", "фон / прошлое", "He has a science background."),
        ("balance", "баланс / равновесие", "Try to balance work and rest."),
        ("barrier", "барьер", "Language can be a barrier."),
        ("basis", "основа", "We meet on a regular basis."),
        ("belief", "убеждение", "It is my firm belief."),
        ("brief", "краткий", "Keep the report brief."),
        ("broad", "широкий", "She has broad knowledge."),
        ("campaign", "кампания", "They ran an ad campaign."),
        ("capacity", "вместимость / способность", "The hall has a large capacity."),
        ("claim", "утверждать / претензия", "He claims to be innocent."),
        ("combine", "объединять", "Combine the two ideas."),
        ("complicated", "сложный", "The rules are complicated."),
        ("concentrate", "концентрироваться", "I can't concentrate here."),
        ("conduct", "проводить (исследование)", "They conducted a survey."),
        ("conflict", "конфликт", "There was a conflict of interest."),
        ("consume", "потреблять", "We consume too much energy."),
        ("contrast", "контраст / противопоставлять", "There is a sharp contrast."),
        ("convince", "убеждать", "She convinced me to stay."),
        ("crucial", "решающий", "This step is crucial."),
        ("debate", "дебаты / спорить", "We had a long debate."),
        ("decade", "десятилетие", "He lived here for a decade."),
        ("demand", "требовать / спрос", "Demand for housing is high."),
        ("despite", "несмотря на", "We went out despite the rain."),
        ("detail", "деталь / подробность", "Tell me every detail."),
        ("determine", "определять", "Genes determine eye colour."),
        ("domestic", "внутренний / домашний", "Domestic flights are cheaper."),
        ("emphasize", "подчёркивать", "She emphasized the main point."),
        ("enormous", "огромный", "It was an enormous effort."),
    ],
    "level_b2": [
        ("abolish", "отменять", "The law was abolished in 1990."),
        ("abundant", "обильный", "Water is abundant here."),
        ("accustomed", "привыкший", "I'm accustomed to early mornings."),
        ("adverse", "неблагоприятный", "Adverse weather delayed us."),
        ("aesthetic", "эстетический", "The design has aesthetic appeal."),
        ("allocate", "распределять", "We allocate funds each year."),
        ("ambition", "амбиция", "Her ambition is to lead the firm."),
        ("analogy", "аналогия", "He drew an analogy with chess."),
        ("arbitrary", "произвольный", "The choice seemed arbitrary."),
        ("articulate", "чётко выражать", "She can articulate her ideas well."),
        ("attain", "достигать", "He attained his goal."),
        ("authentic", "подлинный", "This is an authentic document."),
        ("autonomy", "автономия", "The region has some autonomy."),
        ("bolster", "поддерживать / укреплять", "The news bolstered confidence."),
        ("catalyst", "катализатор", "The crisis was a catalyst for change."),
        ("cease", "прекращать", "The noise finally ceased."),
        ("coincide", "совпадать", "Our holidays coincide this year."),
        ("collaborate", "сотрудничать", "Both teams collaborated closely."),
        ("commence", "начинать", "The course commences in May."),
        ("compel", "принуждать", "Nothing can compel me to agree."),
        ("compile", "составлять / компилировать", "She compiled a list of names."),
        ("complement", "дополнять", "The wine complements the meal."),
        ("comprise", "состоять из", "The team comprises five members."),
        ("conceive", "задумывать / постигать", "He conceived a bold plan."),
        ("concise", "краткий", "Keep your answer concise."),
        ("condemn", "осуждать", "Leaders condemned the attack."),
        ("confine", "ограничивать", "Confine your remarks to the topic."),
        ("conform", "соответствовать", "The product conforms to standards."),
        ("consensus", "консенсус", "We reached a consensus."),
        ("consolidate", "укреплять / объединять", "They consolidated their lead."),
        ("contemplate", "обдумывать", "He contemplated the offer."),
        ("contemporary", "современный", "She studies contemporary art."),
        ("correlate", "коррелировать", "Income correlates with education."),
        ("credible", "правдоподобный", "He gave a credible excuse."),
        ("culminate", "завершаться (чем-то)", "The trip culminated in a feast."),
        ("deem", "считать / полагать", "The plan was deemed risky."),
        ("denote", "обозначать", "Red denotes danger."),
        ("depict", "изображать", "The painting depicts a battle."),
        ("deprive", "лишать", "Don't deprive yourself of sleep."),
        ("detrimental", "вредный", "Stress is detrimental to health."),
    ],
}


def _upsert_word(conn, english: str, translation: str, example: str | None) -> int:
    normalized = english.strip().lower()
    existing = conn.execute(
        sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"),
        {"n": normalized},
    ).first()
    if existing:
        return existing[0]
    row = conn.execute(
        sa.text(
            "INSERT INTO words (track, writing, normalized_word, translation, example_sentence) "
            "VALUES ('en', :w, :n, :t, :e) RETURNING id"
        ),
        {"w": english, "n": normalized, "t": translation, "e": example},
    ).first()
    assert row is not None
    return row[0]


def upgrade() -> None:
    conn = op.get_bind()

    for slug, (new_title, _old) in RENAMES.items():
        conn.execute(
            sa.text("UPDATE packs SET title = :t WHERE slug = :s"),
            {"t": new_title, "s": slug},
        )

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
        for english, translation, example in words:
            wid = _upsert_word(conn, english, translation, example)
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


def downgrade() -> None:
    conn = op.get_bind()
    # Restore old English titles.
    for slug, (_new, old_title) in RENAMES.items():
        conn.execute(
            sa.text("UPDATE packs SET title = :t WHERE slug = :s"),
            {"t": old_title, "s": slug},
        )
    # Remove appended words from level packs, recompute counts.
    for slug, words in EXPANSIONS.items():
        pack = conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": slug}).first()
        if pack is None:
            continue
        pack_id = pack[0]
        normalized = [en.strip().lower() for en, _, _ in words]
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
