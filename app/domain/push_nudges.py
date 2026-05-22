from __future__ import annotations

import random

# Cheeky "you're ignoring me" lines prepended to a push card when the user keeps
# ignoring it. Tone escalates with the ignore count: gentle → cheeky → dramatic.
# Pure + injectable RNG so it's unit-testable. HTML is allowed (cards send with
# parse_mode="HTML").

GENTLE: tuple[str, ...] = (
    "🌱 Эй, не пропадай — слово ждёт тебя!",
    "👀 Я тут карточку принёс, а ты молчишь…",
    "🙂 Маленький повтор — и идём дальше!",
    "✨ Ну же, одно касание — и ты молодец.",
    "🐢 Не спеши… но и не игнорь, ладно?",
    "📚 Слово само себя не выучит 😉",
)

CHEEKY: tuple[str, ...] = (
    "😏 Опять игноришь? Я всё вижу.",
    "🙄 Серьёзно? Я же просто спросил.",
    "😤 Так и будем в молчанку играть?",
    "🫠 Моё терпение, между прочим, не бесконечно.",
    "🍅 Караул, меня игнорируют! Ответь уже.",
    "⏳ Это слово смотрит на тебя с укором.",
)

DRAMATIC: tuple[str, ...] = (
    "💀 Всё. Запоминаю это слово — и тебя заодно.",
    "🚨 Опять?! Я могу заблокировать тебя первым, вообще-то.",
    "😱 Столько раз?! Это уже личное.",
    "🔥 Я не злюсь. Я просто… очень настойчив.",
    "⚰️ Это слово преследует тебя не просто так.",
    "🤖 Сопротивление бесполезно. Жми кнопку.",
)


def _pool(attempts: int) -> tuple[str, ...]:
    if attempts <= 2:
        return GENTLE
    if attempts <= 5:
        return CHEEKY
    return DRAMATIC


def nudge_line(attempts: int, rng: random.Random | None = None) -> str:
    """A nudge to prepend to a re-pushed (ignored) card. `attempts` is how many
    times this same card has been re-sent (1 = first nudge)."""
    n = max(1, attempts)
    chooser = rng.choice if rng is not None else random.choice
    phrase = chooser(_pool(n))
    return f"{phrase}\n<i>повтор №{n}</i>"
