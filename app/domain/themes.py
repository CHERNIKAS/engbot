"""The thematic collections, in the order a beginner should meet them.

Two separate signals decide what gets taught next, and this is the second one.
Corpus rank (`app.domain.ngsl`) says which words a learner will actually meet;
it is built on general *written* English, so it ranks `whether` at 273 and does
not contain `apple` at all. Left alone it would spend a beginner's first month
on `organization` and `performance`.

Themes are the counterweight: concrete, situational vocabulary in the order
teaching practice actually uses it. The grouping follows the Cambridge A2 Key
topic list and the British Council A1-A2 topics — both settled, externally
validated taxonomies rather than our guesses — and the ordering follows the one
principle those sources agree on: start with what a learner can say about
themselves right now, then move outward.

`position` is that order. A theme is not a day; it holds until it is finished,
because switching every morning means never completing anything.

Some words belong to no theme — `become`, `important`, `situation`. That is
expected and fine: they are carried by the corpus-rank stream, which is why
both streams exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    slug: str
    title: str
    hint: str  # what belongs here, for the classifier and for the pack blurb
    # Themes whose members have an order of their own. Sorting numbers by corpus
    # frequency produces «eight, eighteen, eighty, eleven» — alphabetical noise
    # dressed up as a curriculum. Anything not named here keeps the frequency
    # order, which is right for open sets where no intrinsic sequence exists.
    sequence: tuple[str, ...] = ()


# Ordered. Blocks are separated by comment, not by data — the learner sees one
# flat sequence, and a block boundary is not a thing they should have to think
# about.
THEMES: tuple[Theme, ...] = (
    # Building blocks: closed sets, learnable in a sitting, needed by everything after.
    Theme(
        "numbers", "🔢 Числа", "числительные, счёт, количество",
        (
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
            "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
            "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
            "thousand", "million", "zero",
            "first", "second", "third", "fourth", "half", "quarter",
            "number", "count", "amount", "figure", "percent",
        ),
    ),
    Theme("colors", "🎨 Цвета", "цвета и оттенки"),
    Theme(
        "time", "🕐 Время и дни", "часы, дни недели, месяцы, времена года, слова о времени",
        (
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december",
            "spring", "summer", "autumn", "fall", "winter",
            "second", "minute", "hour", "day", "week", "month", "year",
            "morning", "afternoon", "evening", "night", "today", "tomorrow", "yesterday",
        ),
    ),
    # Self and people.
    Theme("family", "👪 Семья и люди", "родственники, друзья, слова о людях и отношениях"),
    Theme("appearance", "🙂 Внешность", "рост, телосложение, волосы, как человек выглядит"),
    Theme("body", "🫀 Тело", "части тела, органы, физические действия тела"),
    Theme("character", "🧠 Характер", "черты личности, поведение, какой человек"),
    # The learner's own day.
    Theme("routine", "☀️ Распорядок дня", "просыпаться, умываться, завтракать, ложиться спать"),
    Theme("home", "🏠 Дом", "комнаты, мебель, части дома"),
    Theme("objects", "🧷 Повседневные вещи", "предметы, которыми пользуются каждый день"),
    # Food.
    Theme("food", "🍎 Еда", "продукты, блюда, фрукты, овощи"),
    Theme("drinks", "☕ Напитки", "напитки и всё, что пьют"),
    Theme("cooking", "🍳 Кухня и готовка", "посуда, приготовление, ресторан, заказ еды"),
    Theme("clothes", "👕 Одежда", "одежда, обувь, аксессуары, размеры"),
    # The world outside the door.
    Theme("city", "🏙 Город", "улицы, здания, городские места"),
    Theme("transport", "🚗 Транспорт", "виды транспорта, поездки по городу, дорога"),
    Theme("shopping", "🛒 Покупки", "магазины, покупка, цены, товары"),
    Theme("money", "💰 Деньги", "деньги, оплата, банк, стоимость"),
    Theme("services", "🏤 Услуги", "почта, банк, парикмахерская, ремонт, обслуживание"),
    # Occupations.
    Theme("work", "💼 Работа", "профессии, офис, карьера, рабочие действия"),
    Theme("education", "🎓 Учёба", "школа, университет, предметы, учебные действия"),
    # The natural world.
    Theme("weather", "🌦 Погода", "погода, осадки, температура"),
    Theme("nature", "🌲 Природа", "ландшафт, растения, море, горы, экология"),
    Theme("animals", "🐘 Животные", "животные, птицы, насекомые, рыбы"),
    Theme("health", "🩺 Здоровье", "болезни, симптомы, врач, лекарства, самочувствие"),
    # Free time.
    Theme("sport", "⚽ Спорт", "виды спорта, спортивные действия, соревнования"),
    Theme("hobby", "🎯 Хобби", "увлечения, отдых, игры, рукоделие"),
    Theme("media", "🎬 Развлечения и медиа", "кино, музыка, книги, телевидение, новости"),
    # Going places.
    Theme("travel", "✈️ Путешествия", "аэропорт, билеты, багаж, поездка за границу"),
    Theme("hotel", "🏨 Отель", "гостиница, бронирование, номер"),
    Theme("countries", "🌍 Страны и языки", "страны, национальности, языки"),
    # Inner life and tools.
    Theme("emotions", "😊 Эмоции", "чувства, настроение, эмоциональные состояния"),
    Theme("tech", "💻 Технологии", "компьютер, интернет, связь, устройства"),
)

BY_SLUG: dict[str, Theme] = {t.slug: t for t in THEMES}

# What the classifier returns for a word that fits no theme. Such words are not
# lost — the corpus-rank stream carries them — so this is a normal outcome and
# not a failure to be retried.
NO_THEME = "none"


def position_of(slug: str) -> int:
    """Teaching order, 0-based. Unknown slugs sort last rather than raising:
    a theme removed from the list must not break a pack that still names it."""
    for i, theme in enumerate(THEMES):
        if theme.slug == slug:
            return i
    return len(THEMES)


def ordered(slug: str, words: list[str]) -> list[str]:
    """Theme words in teaching order.

    A theme with a declared sequence follows it, and anything it does not name
    trails behind in the caller's order — so adding a word to the catalogue
    never silently drops it out of its pack just because the sequence predates
    it. Themes without a sequence are returned untouched.
    """
    theme = BY_SLUG.get(slug)
    if theme is None or not theme.sequence:
        return list(words)
    rank = {w: i for i, w in enumerate(theme.sequence)}
    return sorted(words, key=lambda w: (rank.get(w, len(rank)), words.index(w)))
