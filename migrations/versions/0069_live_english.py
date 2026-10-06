"""«🗣 Живой английский»: 119 conversational phrases, opt-in.

The phrasebook teaches what a traveller needs — the airport, the doctor, the
hotel. It holds almost none of what people say to each other: reactions, small
talk, plans, how they feel, how they text. The owner reviewed this list on
2026-10-06.

Eight packs under their own category, «Живой английский». Only «Темы» and
«Фразы» are stocked automatically (DayPlanService._top_up), so nothing here
reaches a learner who did not add it in «Коллекции»; once added, the phrases
come through the ordinary phrase slot. Positions 0–7 mirror the phrasebook's,
so an added pack alternates with it instead of waiting behind all 102 phrases.

Five single words already in the catalogue as ordinary vocabulary («like» is
«нравиться» there) are taught here as the turns of speech they are in
conversation: «So anyway», «Oh, totally», «So basically», «Well, actually»,
«And I was like».

Revision ID: 0069
Revises: 0068
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

CATEGORY = "Живой английский"

PACKS: list[dict] = [
    {
        "slug": "live_reactions",
        "title": "Реакции",
        "level": "A2",
        "words": [
            ("No way!", "Да ладно!", "No way! You met Taylor Swift?", "Да ладно! Ты встретил Тейлор Свифт?"),
            ("Seriously?", "Серьёзно?", "Seriously? You quit your job?", "Серьёзно? Ты уволился?"),
            ("That's awesome!", "Круто!", "You got the job? That's awesome!", "Тебя взяли? Круто!"),
            ("That's crazy", "С ума сойти", "Ten hours on a bus? That's crazy.", "Десять часов в автобусе? С ума сойти."),
            ("Fair enough", "Справедливо, принято", "You're tired? Fair enough, let's go home.", "Устал? Ладно, принято, пошли домой."),
            ("Makes sense", "Логично", "We leave early to beat the traffic? Makes sense.", "Выезжаем рано, чтобы не стоять в пробках? Логично."),
            ("I'm in", "Я в деле", "Pizza tonight? I'm in.", "Пицца вечером? Я в деле."),
            ("Count me out", "Без меня", "A run at six a.m.? Count me out.", "Пробежка в шесть утра? Без меня."),
            ("Same here", "У меня так же", "I'm so hungry. — Same here.", "Я такой голодный. — У меня так же."),
            ("Me neither", "Я тоже нет", "I don't like horror films. — Me neither.", "Я не люблю ужастики. — Я тоже нет."),
            ("Good for you!", "Рад за тебя!", "I passed my driving test! — Good for you!", "Я сдал на права! — Рад за тебя!"),
            ("Bummer", "Облом", "The concert is cancelled. — Bummer.", "Концерт отменили. — Облом."),
            ("Oh well", "Ну и ладно", "We missed the bus. Oh well, we'll take the next one.", "Мы опоздали на автобус. Ну и ладно, сядем на следующий."),
            ("Whatever", "Без разницы", "Pizza or sushi? — Whatever, I'm not picky.", "Пицца или суши? — Без разницы, я не привередливый."),
            ("Big deal", "Подумаешь", "He has a new car. Big deal.", "У него новая машина. Подумаешь."),
            ("No kidding", "Да ну?", "It's minus thirty outside. — No kidding!", "На улице минус тридцать. — Да ну!"),
            ("You bet", "Ещё бы", "Are you coming to the party? — You bet!", "Придёшь на вечеринку? — Ещё бы!"),
            ("Oh, totally", "Ещё как", "Was the film good? — Oh, totally.", "Фильм хороший? — Ещё как."),
            ("For real?", "Серьёзно?", "I'm moving to Canada. — For real?", "Я переезжаю в Канаду. — Серьёзно?"),
            ("Gotcha", "Понял", "Turn left after the bank. — Gotcha.", "После банка налево. — Понял."),
        ],
    },
    {
        "slug": "live_small_talk",
        "title": "Как дела и что нового",
        "level": "A2",
        "words": [
            ("Long time no see", "Сто лет не виделись", "Hey, Anna! Long time no see!", "Привет, Анна! Сто лет не виделись!"),
            ("What have you been up to?", "Чем занимался?", "So, what have you been up to lately?", "Ну, чем ты занимался в последнее время?"),
            ("How was your weekend?", "Как выходные?", "Hi! How was your weekend?", "Привет! Как выходные?"),
            ("What's new?", "Что нового?", "Hey, what's new with you?", "Привет, что у тебя нового?"),
            ("Not much", "Да ничего особенного", "What's new? — Not much, just work.", "Что нового? — Да ничего особенного, работа."),
            ("Same old, same old", "Всё по-старому", "How's life? — Same old, same old.", "Как жизнь? — Всё по-старому."),
            ("Can't complain", "Не жалуюсь", "How are things? — Can't complain.", "Как дела? — Не жалуюсь."),
            ("Pretty good", "Неплохо", "How was the trip? — Pretty good, thanks.", "Как поездка? — Неплохо, спасибо."),
            ("How's work?", "Как работа?", "How's work these days?", "Как работа в последнее время?"),
            ("Any plans for the weekend?", "Планы на выходные?", "Any plans for the weekend? — Not yet.", "Планы на выходные? — Пока нет."),
            ("What do you do?", "Кем работаешь?", "So, what do you do? — I'm a nurse.", "А ты кем работаешь? — Я медсестра."),
            ("Where are you from?", "Откуда ты?", "Where are you from? — I'm from Kazan.", "Откуда ты? — Я из Казани."),
            ("Good to see you", "Рад видеть", "Good to see you again!", "Рад снова тебя видеть!"),
            ("It's been ages", "Целую вечность не виделись", "Wow, it's been ages! How are you?", "Ого, целую вечность не виделись! Как ты?"),
            ("Take it easy", "Бывай, не напрягайся", "See you tomorrow. Take it easy!", "До завтра. Бывай!"),
            ("Have a good one", "Хорошего дня", "Thanks for the coffee. Have a good one!", "Спасибо за кофе. Хорошего дня!"),
            ("Talk to you later", "Поговорим позже", "I have to go. Talk to you later!", "Мне пора. Поговорим позже!"),
            ("Keep in touch", "Не пропадай", "Good luck in London! Keep in touch.", "Удачи в Лондоне! Не пропадай."),
            ("Say hi to Tom for me", "Передавай привет Тому", "Say hi to Tom for me!", "Передавай привет Тому!"),
        ],
    },
    {
        "slug": "live_opinion",
        "title": "Мнение и согласие",
        "level": "A2",
        "words": [
            ("I guess so", "Наверное", "Is it going to rain? — I guess so.", "Будет дождь? — Наверное."),
            ("I'm not sure about that", "Не уверен", "It's cheaper online. — I'm not sure about that.", "В интернете дешевле. — Не уверен."),
            ("I don't think so", "Не думаю", "Is the shop open now? — I don't think so.", "Магазин сейчас открыт? — Не думаю."),
            ("Exactly!", "Вот именно!", "So we need more time? — Exactly!", "Значит, нам нужно больше времени? — Вот именно!"),
            ("You're right", "Ты прав", "You're right, it was my fault.", "Ты прав, это моя вина."),
            ("Good point", "Хорошее замечание", "But the train is faster. — Good point.", "Но поезд быстрее. — Хорошее замечание."),
            ("That's true", "Это правда", "London is expensive. — That's true.", "Лондон дорогой. — Это правда."),
            ("I see what you mean", "Понимаю, о чём ты", "I see what you mean, but I still want to try.", "Понимаю, о чём ты, но всё равно хочу попробовать."),
            ("Not really", "Не особо", "Do you like jazz? — Not really.", "Тебе нравится джаз? — Не особо."),
            ("Kind of", "Типа того", "Are you tired? — Kind of.", "Устал? — Типа того."),
            ("It's up to you", "Тебе решать", "Cinema or bowling? It's up to you.", "Кино или боулинг? Тебе решать."),
            ("I don't mind", "Я не против", "Can I open the window? — I don't mind.", "Можно открыть окно? — Я не против."),
            ("Either is fine", "Любой подойдёт", "Tea or coffee? — Either is fine.", "Чай или кофе? — Любой подойдёт."),
            ("Let's see", "Посмотрим", "Will you come tomorrow? — Let's see.", "Придёшь завтра? — Посмотрим."),
            ("Let me think", "Дай подумать", "What do you want for your birthday? — Let me think.", "Что хочешь на день рождения? — Дай подумать."),
        ],
    },
    {
        "slug": "live_plans",
        "title": "Планы и встречи",
        "level": "A2",
        "words": [
            ("Are you free tonight?", "Свободен вечером?", "Are you free tonight? Let's get dinner.", "Свободен вечером? Пойдём поужинаем."),
            ("Let's grab a coffee", "Пойдём выпьем кофе", "Let's grab a coffee after work.", "Пойдём выпьем кофе после работы."),
            ("Want to hang out?", "Потусим?", "I'm bored. Want to hang out?", "Мне скучно. Потусим?"),
            ("I'm down", "Я за", "Karaoke tonight? — I'm down!", "Караоке вечером? — Я за!"),
            ("I can't make it", "Не смогу прийти", "Sorry, I can't make it on Friday.", "Прости, в пятницу не смогу прийти."),
            ("Rain check?", "Перенесём?", "I'm sick today. Rain check?", "Я сегодня заболел. Перенесём?"),
            ("On my way", "Уже еду", "On my way! See you in ten minutes.", "Уже еду! Увидимся через десять минут."),
            ("I'm running late", "Опаздываю", "Sorry, I'm running late. Start without me.", "Прости, опаздываю. Начинайте без меня."),
            ("Be there in five", "Буду через пять минут", "Wait for me, I'll be there in five.", "Подожди меня, буду через пять минут."),
            ("Hurry up!", "Поторопись!", "Hurry up! The film starts in five minutes.", "Поторопись! Фильм начинается через пять минут."),
            ("Take your time", "Не торопись", "Take your time, I'm not in a hurry.", "Не торопись, я никуда не спешу."),
            ("No rush", "Не спеши", "Send it tomorrow, no rush.", "Пришли завтра, не спеши."),
            ("Wait a sec", "Секунду", "Wait a sec, I'll get my keys.", "Секунду, возьму ключи."),
            ("Let me know", "Дай знать", "Let me know when you get home.", "Дай знать, когда доберёшься домой."),
            ("Sounds like a plan", "Договорились", "Meet at the station at seven? — Sounds like a plan.", "Встречаемся на станции в семь? — Договорились."),
        ],
    },
    {
        "slug": "live_feelings",
        "title": "Чувства",
        "level": "A2",
        "words": [
            ("I'm so tired", "Я так устал", "I'm so tired, I'm going to bed.", "Я так устал, пойду спать."),
            ("I'm starving", "Умираю с голоду", "Let's eat, I'm starving!", "Давай поедим, я умираю с голоду!"),
            ("I'm exhausted", "Я выжат", "After the move I'm exhausted.", "После переезда я выжат."),
            ("I'm bored", "Мне скучно", "There's nothing to do. I'm bored.", "Заняться нечем. Мне скучно."),
            ("I'm stressed out", "Я на нервах", "Exams next week. I'm stressed out.", "Экзамены на следующей неделе. Я на нервах."),
            ("I'm freaking out", "Я в панике", "I can't find my passport. I'm freaking out!", "Не могу найти паспорт. Я в панике!"),
            ("I'm so excited", "Жду не дождусь", "We fly to Rome tomorrow. I'm so excited!", "Завтра летим в Рим. Жду не дождусь!"),
            ("I can't wait!", "Скорей бы!", "Holidays start on Monday. I can't wait!", "Каникулы с понедельника. Скорей бы!"),
            ("It's driving me crazy", "Это сводит меня с ума", "The noise upstairs is driving me crazy.", "Шум сверху сводит меня с ума."),
            ("I'm fed up with it", "Достало", "Rain again? I'm fed up with it.", "Опять дождь? Достало."),
            ("I'm over it", "Я это пережил", "The breakup was hard, but I'm over it now.", "Расставание было тяжёлым, но я это пережил."),
            ("Cheer up!", "Не грусти!", "Cheer up! It's not the end of the world.", "Не грусти! Это не конец света."),
            ("Don't worry about it", "Не парься", "Sorry I'm late. — Don't worry about it.", "Прости, что опоздал. — Не парься."),
            ("Calm down", "Успокойся", "Calm down, we'll find your phone.", "Успокойся, найдём мы твой телефон."),
            ("Hang in there", "Держись", "Only one more week of work. Hang in there!", "Осталась одна рабочая неделя. Держись!"),
        ],
    },
    {
        "slug": "live_texting",
        "title": "Переписка",
        "level": "B1",
        "words": [
            ("BTW", "Кстати", "BTW, I'm bringing pizza.", "Кстати, я принесу пиццу."),
            ("IDK", "Не знаю", "Where are we meeting? — IDK, you choose.", "Где встречаемся? — Не знаю, выбирай ты."),
            ("LOL", "Ахах", "He fell asleep in the meeting LOL", "Он уснул на совещании, ахах"),
            ("OMG", "Боже", "OMG, did you see the news?", "Боже, ты видел новости?"),
            ("TBH", "Честно говоря", "TBH, I didn't like the film.", "Честно говоря, фильм мне не понравился."),
            ("ASAP", "Как можно скорее", "Call me back ASAP.", "Перезвони как можно скорее."),
            ("FYI", "К сведению", "FYI, the meeting moved to Monday.", "К сведению: встречу перенесли на понедельник."),
            ("BRB", "Сейчас вернусь", "BRB, someone's at the door.", "Сейчас вернусь, кто-то в дверь звонит."),
            ("NVM", "Неважно", "Where's my charger? NVM, found it.", "Где моя зарядка? Неважно, нашёл."),
            ("IMO", "По-моему", "IMO, the first season was better.", "По-моему, первый сезон был лучше."),
            ("TTYL", "Поговорим позже", "Gotta go, TTYL!", "Мне пора, поговорим позже!"),
            ("THX", "Спасибо", "Got the photos, thx!", "Фотки получил, спасибо!"),
            ("PLS", "Пожалуйста", "Pls send me the address.", "Пришли мне адрес, пожалуйста."),
            ("JK", "Шучу", "You're the worst cook ever. JK, it was great!", "Ты худший повар на свете. Шучу, было отлично!"),
            ("DM me", "Напиши в личку", "Want the recipe? DM me.", "Хочешь рецепт? Напиши в личку."),
        ],
    },
    {
        "slug": "live_fillers",
        "title": "Связки в речи",
        "level": "B1",
        "words": [
            ("So anyway", "Короче, в общем", "So anyway, we got lost and came home at midnight.", "Короче, мы заблудились и вернулись домой в полночь."),
            ("Well, actually", "Вообще-то", "Well, actually, I've never been to Paris.", "Вообще-то я никогда не был в Париже."),
            ("So basically", "Короче, по сути", "So basically, we need to start again.", "Короче, по сути, надо начинать заново."),
            ("And I was like", "А я такой", "He said he was leaving, and I was like, what?", "Он сказал, что уходит, а я такой: что?"),
            ("You know", "Ну, знаешь", "It was, you know, a bit weird.", "Это было, ну, знаешь, немного странно."),
            ("I mean", "То есть", "It's fine. I mean, it's not perfect.", "Нормально. То есть не идеально."),
            ("So yeah", "Ну вот", "So yeah, that's my new job.", "Ну вот, такая у меня новая работа."),
            ("Sort of", "Вроде того", "It's sort of a café and a bookshop.", "Это вроде как кафе и книжный."),
            ("To be honest", "Если честно", "To be honest, I forgot.", "Если честно, я забыл."),
            ("By the way", "Кстати", "By the way, how's your sister?", "Кстати, как твоя сестра?"),
        ],
    },
    {
        "slug": "live_slang",
        "title": "Лёгкий сленг",
        "level": "B1",
        "words": [
            ("That's sick", "Это огонь", "Your new bike? That's sick!", "Твой новый байк? Это огонь!"),
            ("It's a piece of cake", "Проще простого", "The test? It's a piece of cake.", "Тест? Проще простого."),
            ("It's not my thing", "Это не моё", "Thanks, but dancing is not my thing.", "Спасибо, но танцы — это не моё."),
            ("I'm broke", "Я на мели", "I can't go out, I'm broke until Friday.", "Не могу никуда пойти, я на мели до пятницы."),
            ("Chill", "Расслабься", "Chill, we have plenty of time.", "Расслабься, у нас полно времени."),
            ("Cool!", "Круто!", "We're going to the beach? Cool!", "Едем на пляж? Круто!"),
            ("Awesome", "Офигенно", "The concert was awesome.", "Концерт был офигенный."),
            ("My treat", "Я угощаю", "Put your wallet away, it's my treat.", "Убери кошелёк, я угощаю."),
            ("Cheers", "Спасибо / будем", "Here's your coffee. — Cheers!", "Вот твой кофе. — Спасибо!"),
            ("No big deal", "Ничего страшного", "I broke a glass. — No big deal.", "Я разбил стакан. — Ничего страшного."),
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for position, pack in enumerate(PACKS):
        if conn.execute(sa.text("SELECT id FROM packs WHERE slug = :s"), {"s": pack["slug"]}).first():
            continue
        word_ids: list[int] = []
        for english, russian, example_en, example_ru in pack["words"]:
            normalized = english.strip().lower()
            existing = conn.execute(
                sa.text("SELECT id FROM words WHERE track = 'en' AND normalized_word = :n"),
                {"n": normalized},
            ).first()
            if existing:
                raise RuntimeError(f"{english!r} is already in the catalogue — pick another form")
            row = conn.execute(
                sa.text(
                    "INSERT INTO words (track, writing, normalized_word, translation, level, is_phrase,"
                    " example_sentence, abstract_example_en, abstract_example_ru)"
                    " VALUES ('en', :w, :n, :t, :lvl, true, :ex, :ex, :exru) RETURNING id"
                ),
                {"w": english, "n": normalized, "t": russian, "lvl": pack["level"],
                 "ex": example_en, "exru": example_ru},
            ).first()
            word_ids.append(row[0])
        pack_id = conn.execute(
            sa.text(
                "INSERT INTO packs (slug, track, title, description, category, words_count, is_active, position)"
                " VALUES (:slug, 'en', :title, :d, :cat, :n, true, :pos) RETURNING id"
            ),
            {"slug": pack["slug"], "title": pack["title"], "d": "Живая разговорная речь.",
             "cat": CATEGORY, "n": len(word_ids), "pos": position},
        ).first()[0]
        for i, wid in enumerate(word_ids):
            conn.execute(
                sa.text("INSERT INTO pack_words (pack_id, word_id, position) VALUES (:p, :w, :i)"),
                {"p": pack_id, "w": wid, "i": i},
            )


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [p["slug"] for p in PACKS]
    word_ids = [
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT pw.word_id FROM pack_words pw JOIN packs p ON p.id = pw.pack_id WHERE p.slug IN :s"
            ).bindparams(sa.bindparam("s", expanding=True)),
            {"s": slugs},
        )
    ]
    conn.execute(
        sa.text("DELETE FROM pack_words WHERE pack_id IN (SELECT id FROM packs WHERE slug IN :s)").bindparams(
            sa.bindparam("s", expanding=True)
        ),
        {"s": slugs},
    )
    conn.execute(
        sa.text("DELETE FROM packs WHERE slug IN :s").bindparams(sa.bindparam("s", expanding=True)),
        {"s": slugs},
    )
    if word_ids:
        for table in ("word_reviews", "user_words"):
            conn.execute(
                sa.text(
                    f"DELETE FROM {table} WHERE "
                    + ("user_word_id IN (SELECT id FROM user_words WHERE word_id IN :w)" if table == "word_reviews" else "word_id IN :w")
                ).bindparams(sa.bindparam("w", expanding=True)),
                {"w": word_ids},
            )
        conn.execute(
            sa.text("DELETE FROM words WHERE id IN :w").bindparams(sa.bindparam("w", expanding=True)),
            {"w": word_ids},
        )
