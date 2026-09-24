"""The words the thematic collections could not be built without.

The themes were rebuilt against the Cambridge A2 Key and British Council topic
lists, and measuring the catalogue against that core showed 496 words a learner
needs to handle these situations. 417 were already present — 124 of them merely
filed under a neighbouring theme — and 78 were missing outright.

They are not padding. An earlier plan targeted a flat 40 words per theme, which
would have meant generating roughly 495 and inventing filler for closed sets:
`colors` is complete at 16 entries and adding turquoise would repeat the exact
mistake this rework exists to fix. These 78 are the opposite case — the months
of the year, the numbers past twelve, the nationalities, and the words without
which a hotel or a post office cannot be described at all:

    hotel had `hotel`, `reservation`, `reserve` and nothing else
    services had no `hairdresser`, no `parcel`, no `appointment`
    numbers stopped at twelve, with no `zero`, `thirty` or `fifty`

Generated and verified by the same pipeline as migration 0047: a short Russian
gloss with no Latin in it, an example containing the word in a form the cloze
masker can blank, and a hint that does not contain the answer.

Revision ID: 0048
Revises: 0047
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

# (writing, translation, level, polysemous, example, hint_en, hint_ru)
WORDS: tuple[tuple, ...] = (
    ("appointment", "встреча / запись на прием", "B1", False, "I have an appointment with the doctor at ten.",
     "This is a time you plan to meet someone for a service.", "Это время, когда вы планируете встретиться с кем-то для получения услуги."),
    ("april", "апрель", "A1", False, "My birthday is in April.",
     "My birthday is the month after March.", "Мой день рождения в месяце после марта."),
    ("august", "август", "A1", False, "We go to the beach in August.",
     "We go to the beach in the month after July.", "Мы ходим на пляж в месяце после июля."),
    ("autumn", "осень", "A1", False, "The leaves fall in the autumn.",
     "The leaves fall in the season before winter.", "Листья падают в сезоне перед зимой."),
    ("bike", "велосипед", "A1", False, "My brother rides his bike to school.",
     "You sit on it and use your feet to move.", "Ты садишься на него и используешь ноги, чтобы ехать."),
    ("cashier", "кассир", "A2", False, "The cashier takes my money at the shop desk.",
     "This person works at the shop and takes money from customers.", "Этот человек работает в магазине и принимает деньги от покупателей."),
    ("channel", "канал / русло", "B1", True, "I like to change the channel on the TV.",
     "This is a specific station you watch on your television set.", "Это конкретная станция, которую вы смотрите по телевизору."),
    ("check-in", "регистрация", "A2", False, "We go to the hotel for check-in at two.",
     "You tell the people at the hotel that you are here.", "Вы сообщаете сотрудникам отеля о своем прибытии."),
    ("check-out", "выписка / расчетный час", "A2", False, "The check-out time is at ten in the morning.",
     "You pay your bill and leave the room on the last day.", "Вы оплачиваете счет и покидаете номер в последний день."),
    ("chinese", "китайский", "A1", False, "I like to eat tasty Chinese food.",
     "This language is from a very big country in Asia.", "Этот язык из очень большой страны в Азии."),
    ("cinema", "кинотеатр", "A1", False, "We go to the cinema to watch a new movie.",
     "This is a place where people sit in the dark to see films.", "Это место, где люди сидят в темноте, чтобы посмотреть фильмы."),
    ("click", "щелчок / нажимать", "A2", True, "Please click the button to open the file.",
     "Push the mouse button to select something on a screen.", "Нажмите кнопку мыши, чтобы выбрать что-то на экране."),
    ("coin", "монета", "A2", False, "I have one small gold coin in my pocket.",
     "This is round metal money that you use to pay.", "Это круглые металлические деньги, которые вы используете для оплаты."),
    ("december", "декабрь", "A1", False, "Christmas is in december.",
     "The last month of the year.", "Последний месяц года."),
    ("depart", "отправляться / уезжать", "B1", False, "The train will depart from the station very soon.",
     "This means the vehicle is going to start its journey now.", "Это значит, что транспортное средство сейчас начинает свой путь."),
    ("eight", "восемь", "A1", False, "I have eight red apples in my bag.",
     "I have one plus seven red apples in my bag.", "У меня в сумке семь плюс одно красное яблоко."),
    ("eighteen", "восемнадцать", "A1", False, "My brother is eighteen years old today.",
     "My brother is two years younger than twenty today.", "Моему брату сегодня на два года меньше двадцати."),
    ("eighty", "восемьдесят", "A1", False, "The old man is eighty years old.",
     "The old man is ten years younger than ninety.", "Этому старику на десять лет меньше девяноста."),
    ("eleven", "одиннадцать", "A1", False, "There are eleven players in a football team.",
     "There are ten plus one players in a football team.", "В футбольной команде десять плюс один игрок."),
    ("email", "электронная почта", "A1", False, "Please send me an email about the meeting.",
     "This is a digital letter that you send using the internet.", "Это цифровое письмо, которое вы отправляете через интернет."),
    ("english", "английский", "A1", False, "I speak English with my friends every day.",
     "This is the language of people in the UK and USA.", "Это язык, на котором говорят люди в Великобритании и США."),
    ("fair", "справедливый / ярмарка", "A2", True, "The teacher is fair to all the students in class.",
     "He gives the same rules to everyone.", "Он устанавливает одинаковые правила для всех."),
    ("february", "февраль", "A1", False, "My birthday is in february.",
     "The month after January.", "Месяц после января."),
    ("fifteen", "пятнадцать", "A1", False, "She is fifteen minutes late for school.",
     "She is ten plus five minutes late for school.", "Она опаздывает в школу на десять плюс пять минут."),
    ("fifty", "пятьдесят", "A1", False, "I have fifty dollars in my pocket.",
     "I have five times ten dollars in my pocket.", "У меня в кармане пять раз по десять долларов."),
    ("fork", "вилка", "A1", False, "I use a fork to eat my dinner today.",
     "You use this thing to pick up food to eat.", "Ты используешь эту вещь, чтобы подцеплять еду."),
    ("forty", "сорок", "A1", False, "The bus comes in forty minutes.",
     "The bus comes in four times ten minutes.", "Автобус приедет через четыре раза по десять минут."),
    ("fourteen", "четырнадцать", "A1", False, "I read fourteen pages of this book.",
     "I read ten plus four pages of this book.", "Я прочитал десять плюс четыре страницы этой книги."),
    ("french", "французский", "A1", False, "She wants to learn to speak French.",
     "The language that people speak in Paris.", "Язык, на котором говорят в Париже."),
    ("german", "немецкий", "A1", False, "My friend studies the German language.",
     "The language used in Berlin and Vienna.", "Язык, на котором говорят в Берлине и Вене."),
    ("glasses", "очки / стаканы", "A1", True, "I wear glasses to read.",
     "Things you put on your eyes to see better.", "Вещи, которые надеваешь на глаза, чтобы лучше видеть."),
    ("guest", "гость / постоялец", "A1", False, "Every guest gets a key to the room.",
     "A person who stays in a hotel for a night.", "Человек, который останавливается в отеле на ночь."),
    ("hairdresser", "парикмахер", "A2", False, "The hairdresser cuts my hair today.",
     "This person makes your hair look good.", "Этот человек делает так, чтобы твои волосы выглядели хорошо."),
    ("handsome", "красивый", "A2", False, "He is a very handsome man.",
     "He looks very good and attractive.", "Он выглядит очень хорошо и привлекательно."),
    ("hardworking", "трудолюбивый", "A2", False, "He is a hardworking student.",
     "He works a lot and does his best.", "Он много работает и старается."),
    ("insect", "насекомое", "A2", False, "I see a small insect on the grass.",
     "A little animal with six legs.", "Маленькое животное с шестью лапками."),
    ("italian", "итальянский", "A1", False, "We love to eat Italian pizza.",
     "The language from the country with Rome.", "Язык из страны, где находится Рим."),
    ("january", "январь", "A1", False, "It is very cold in january.",
     "The first month of the year.", "Первый месяц года."),
    ("japanese", "японский", "A1", False, "He likes to watch Japanese cartoons.",
     "The language spoken in Tokyo.", "Язык, на котором говорят в Токио."),
    ("july", "июль", "A1", False, "We go to the beach in july.",
     "A hot summer month after June.", "Жаркий летний месяц после июня."),
    ("june", "июнь", "A1", False, "School finishes in june.",
     "The month when summer begins.", "Месяц, когда начинается лето."),
    ("living room", "гостиная", "A1", False, "We watch TV in the living room every night.",
     "It is the big room where the family sits together.", "Это большая комната, где вся семья сидит вместе."),
    ("march", "март", "A1", True, "Flowers grow in march.",
     "The first month of spring.", "Первый месяц весны."),
    ("may", "май", "A1", True, "The weather is nice in may.",
     "The month before June.", "Месяц перед июнем."),
    ("menu", "меню", "A1", False, "Please look at the menu to choose your lunch.",
     "This paper lists all the food you can buy at a restaurant.", "В этом документе перечислены все блюда, которые можно купить в ресторане."),
    ("nationality", "национальность", "A2", False, "Please write your nationality on the paper.",
     "The name of the country where you are from.", "Название страны, из которой вы родом."),
    ("nineteen", "девятнадцать", "A1", False, "She is nineteen years old this month.",
     "She is one year younger than twenty this month.", "Ей в этом месяце на год меньше двадцати."),
    ("ninety", "девяносто", "A1", False, "The test has ninety questions to answer.",
     "The test has ten less than one hundred questions.", "В тесте на десять меньше ста вопросов."),
    ("november", "ноябрь", "A1", False, "It often rains in november.",
     "The month before December.", "Месяц перед декабрем."),
    ("october", "октябрь", "A1", False, "The leaves fall in october.",
     "The month after September.", "Месяц после сентября."),
    ("offline", "офлайн / вне сети", "A2", False, "I work offline when I have no internet.",
     "You are not connected to the internet right now.", "Вы не подключены к интернету в данный момент."),
    ("online", "онлайн / в сети", "A2", False, "We can buy clothes online today.",
     "You use the internet to do something.", "Вы используете интернет, чтобы что-то сделать."),
    ("parcel", "посылка / участок", "B1", True, "I received a large parcel from my friend yesterday.",
     "This is a box or a bag sent by mail to your home.", "Это коробка или сумка, присланная почтой к вам домой."),
    ("pasta", "макароны", "A1", False, "We eat pasta for dinner.",
     "Italian food made from flour and water.", "Итальянская еда из муки и воды."),
    ("pet", "домашний питомец", "A1", False, "My dog is a good pet.",
     "An animal that lives in your house.", "Животное, которое живет у тебя дома."),
    ("plate", "тарелка", "A1", True, "Put the food on the blue plate.",
     "You use this to eat your dinner.", "Ты используешь это, чтобы съесть свой ужин."),
    ("rainy", "дождливый", "A1", False, "It is very rainy and cold outside today.",
     "This means there is a lot of water falling from the sky.", "Это означает, что с неба падает много воды."),
    ("receipt", "чек", "A2", False, "Do not forget to take your receipt after shopping.",
     "This small piece of paper shows what you bought and the cost.", "Этот маленький клочок бумаги показывает, что вы купили и сколько это стоило."),
    ("reception", "стойка регистрации / приемная", "A2", False, "Please leave your key at the reception.",
     "This is the place where you ask for help in a hotel.", "Это место в отеле, где можно попросить о помощи."),
    ("russian", "русский", "A1", False, "My teacher is from a Russian city.",
     "The language that people speak in Moscow.", "Язык, на котором говорят в Москве."),
    ("scared", "испуганный", "A2", False, "The dog was scared of the loud noise.",
     "You feel this when you are afraid of something.", "Вы чувствуете это, когда чего-то боитесь."),
    ("september", "сентябрь", "A1", False, "School starts again in september.",
     "The month when autumn begins.", "Месяц, когда начинается осень."),
    ("seventeen", "семнадцать", "A1", False, "He is seventeen years old now.",
     "He is three years younger than twenty now.", "Ему сейчас на три года меньше двадцати."),
    ("seventy", "семьдесят", "A1", False, "The train ticket costs seventy dollars.",
     "The train ticket costs ten less than eighty dollars.", "Билет на поезд стоит на десять меньше восьмидесяти долларов."),
    ("sixteen", "шестнадцать", "A1", False, "My sister is sixteen years old.",
     "My sister is four years younger than twenty.", "Моей сестре на четыре года меньше двадцати."),
    ("sixty", "шестьдесят", "A1", False, "There are sixty minutes in one hour.",
     "There are six times ten minutes in one hour.", "В одном часе шесть раз по десять минут."),
    ("slim", "стройный", "A2", False, "She is tall and slim.",
     "She is thin in a healthy way.", "Она худая в здоровом смысле."),
    ("soda", "газировка", "A2", False, "Do you want some soda?",
     "A sweet and bubbly cold drink.", "Сладкий газированный холодный напиток."),
    ("spanish", "испанский", "A1", False, "They like to listen to Spanish music.",
     "The language spoken in Madrid.", "Язык, на котором говорят в Мадриде."),
    ("spider", "паук", "A2", False, "I see a big black spider on the wall.",
     "This is an animal with eight legs that makes a web.", "Это животное с восемью ногами, которое плетет паутину."),
    ("supermarket", "супермаркет", "A1", False, "I buy milk at the supermarket.",
     "A big store where you can buy food.", "Большой магазин, где можно купить еду."),
    ("t-shirt", "футболка", "A1", False, "I like my red t-shirt.",
     "You wear this on your body in summer.", "Ты носишь это на теле летом."),
    ("thirteen", "тринадцать", "A1", False, "He is thirteen years old today.",
     "He is three years older than ten today.", "Ему сегодня на три года больше десяти."),
    ("thirty", "тридцать", "A1", False, "I wait for thirty minutes at home.",
     "I wait for three times ten minutes at home.", "Я жду дома три раза по десять минут."),
    ("umbrella", "зонтик", "A1", False, "Take your umbrella because it is raining outside now.",
     "You hold this over your head when it rains.", "Ты держишь это над головой, когда идет дождь."),
    ("wifi", "вай-фай / беспроводная сеть", "A2", False, "Does this hotel have free wifi?",
     "A way to use the internet without any wires.", "Способ пользоваться интернетом без проводов."),
    ("wild", "дикий", "A2", False, "The lion is a wild animal.",
     "It does not live with people.", "Оно не живет с людьми."),
    ("zero", "ноль", "A1", False, "I have zero apples in my bag today.",
     "I do not have any apples with me right now.", "У меня сейчас с собой нет ни одного яблока."),)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO words (track, writing, normalized_word, translation, level,"
            " ngsl_rank, polysemous, example_sentence, abstract_example_en,"
            " abstract_example_ru, is_function_word)"
            " VALUES ('en', :w, :norm, :t, :lvl, NULL, :poly, :ex, :hen, :hru, false)"
            " ON CONFLICT (track, normalized_word) DO NOTHING"
        ),
        [
            {"w": w, "norm": w.lower(), "t": t, "lvl": lvl, "poly": poly, "ex": ex, "hen": hen, "hru": hru}
            for w, t, lvl, poly, ex, hen, hru in WORDS
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM words WHERE track = 'en' AND normalized_word = ANY(:names)"),
        {"names": [w.lower() for w, *_ in WORDS]},
    )
