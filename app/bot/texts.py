from __future__ import annotations

# Russian text constants — kept centralised so we can localise later.

PASSWORD_PROMPT = "🔒 Доступ по паролю. Введи его, пожалуйста 🙏"
PASSWORD_WRONG = "🙈 Неверный пароль. Попробуй ещё раз."
PASSWORD_OK = "✨ Пароль принят! Добро пожаловать 🌸"
PASSWORD_REQUIRED_HINT = "🔒 Доступ закрыт. Отправь /start и введи пароль."

INTRO = (
    "🌸 <b>Lazy Bot</b> — твой персональный словарик и тренажёр английского.\n\n"
    "Добавляй слова, импортируй TXT, выбирай тематические паки — а учить их "
    "поможем умными повторениями. Поехали? ✨"
)

ASK_TRACKS = "Что будем учить? 📚"
ASK_DAILY_GOAL = "Сколько слов в день хочешь учить? 🎯"
ASK_CUSTOM_GOAL = "Введи число от 1 до 100 ✍️"
ERROR_GOAL_TOO_SMALL = "🤏 Маловато. Выбери число от 1 до 100."
ERROR_GOAL_TOO_BIG = "🥵 Многовато для комфортной учёбы. Выбери от 1 до 100."
ERROR_GOAL_NOT_NUMBER = "🤔 Это не число. Введи целое от 1 до 100."

ONBOARDING_DONE = "🎉 Всё настроено! Удачной учёбы 🌸"

# Placement test — gives the picker a level to aim at.
PLACEMENT_INTRO = (
    "Давай прикинем твой уровень 📏\n\n"
    "Буду показывать слова и подбирать сложность по ходу — справляешься, "
    "даю сложнее; не идёт, беру попроще.\n\n"
    "Не знаешь слово — жми «Не знаю», это тоже ответ, а не ошибка. "
    "Обычно хватает 6–9 слов."
)
# No fixed length to promise: the staircase stops as soon as the level is
# bracketed, so the card counts questions instead of pretending to know the end.
PLACEMENT_CARD = "<b>{writing}</b>\n\nЧто это значит?   (вопрос {position})"
PLACEMENT_RESULT = (
    "Готово! Твой уровень — <b>{level}</b> ✨\n\n"
    "Буду подбирать слова под него: в основном по уровню, "
    "иногда чуть проще, иногда на вырост."
)
PLACEMENT_UNAVAILABLE = (
    "🌿 Тест сейчас не собрать — не хватает слов в каталоге.\n\n"
    "Это на моей стороне, не на твоей. Поставил средний уровень, чтобы не "
    "задерживать: слова будут подбираться по нему.\n\n"
    "Загляни в Настройки → «📏 Мой уровень» попозже — тест там появится."
)
# Telegram caps a callback alert at 200 characters, so the same explanation
# can't be reused there — a silently truncated apology is worse than a short one.
PLACEMENT_UNAVAILABLE_SHORT = "🌿 Тест сейчас не собрать — не хватает слов. Загляни попозже."
PLACEMENT_DONT_KNOW = "🤷 Не знаю"

# Settings → «📏 Мой уровень»
LEVEL_SCREEN = (
    "📏 Твой уровень: <b>{level}</b>\n\n"
    "Первая тысяча частотных слов: <b>{band1}</b> из {band1_total}\n"
    "Вторая тысяча: <b>{band2}</b> из {band2_total}\n\n"
    "Уровень считается по этим числам — по нему подбираются новые слова.\n\n"
    "<i>Отдельно настраивать его не нужно: бот пересчитывает сам, раз в день.</i>"
)
LEVEL_SCREEN_UNSET = LEVEL_SCREEN
LEVEL_UPDATED = "Готово! Теперь твой уровень — <b>{level}</b> ✨"

# Placement gate — shown to users who predate the test and haven't taken it.
PLACEMENT_GATE = (
    "📏 Бот научился подбирать слова под уровень\n\n"
    "Раньше он выдавал их подряд — половина была либо слишком простой, "
    "либо слишком сложной. Теперь смотрит, что ты уже знаешь.\n\n"
    "Осталось узнать твой уровень: 6–9 слов, минута. "
    "Пока его нет, подбирать не из чего — поэтому карточки ждут."
)
PLACEMENT_GATE_HINT = "Сначала пройди тест на уровень 📏"
PLACEMENT_GATE_START = "Пройти тест ▶️"
PLACEMENT_GATE_DONE = (
    "Готово! Твой уровень — <b>{level}</b> ✨\n\n"
    "Теперь слова подбираются под него. Возвращаемся к учёбе 🌿"
)

MAIN_MENU = "Главное меню 🌸"

# Persistent bottom reply-keyboard buttons (main navigation).
#
# Named after what the learner came to do, not after the machinery: the day is
# «Сегодня», not «Курс», because the plan is the thing they finish. The pack
# browser is «Коллекции» because a «пак» is our word, not theirs.
BTN_TODAY = "📅 Сегодня"
BTN_MY_WORDS = "📚 Мой словарь"
BTN_COLLECTIONS = "🗂 Коллекции"
BTN_GRAMMAR = "📖 Грамматика"
BTN_PROGRESS = "📊 Прогресс"
BTN_SETTINGS = "⚙️ Настройки"

# Superseded labels. Telegram keeps a reply keyboard on the client until the
# next one is sent, so whoever last opened the bot still has the old buttons on
# screen — these keep those taps working instead of falling through to
# "add a word".
BTN_WORDS = "🗂 Слова"
BTN_STUDY = "🔥 Учить"
BTN_ADD = "➕ Добавить слова"
BTN_IMPORT = "📂 Импорт TXT"
BTN_PACKS = "📦 Паки"
BTN_HELP = "❓ Справка"
BTN_MY_WORDS_OLD = "📚 Мои слова"
# Bottom-menu taps allowed in any state (treated as a reset). Includes the
# legacy single-action labels so older messages / deep links still navigate.
MENU_BUTTON_TEXTS: frozenset[str] = frozenset(
    {
        BTN_TODAY, BTN_MY_WORDS, BTN_COLLECTIONS, BTN_GRAMMAR, BTN_PROGRESS, BTN_SETTINGS,
        BTN_WORDS, BTN_STUDY, BTN_ADD, BTN_IMPORT, BTN_PACKS, BTN_HELP, BTN_MY_WORDS_OLD,
    }
)
MENU_PLACEHOLDER = "Выбери действие 🌸"

TODAY_NO_PLAN = (
    "📅 <b>Сегодня</b>\n\n"
    "План ещё не собран — он появится с первой карточкой дня 🌿\n"
    "<i>Карточки приходят сами, в твоё окно из настроек.</i>"
)

WORDS_MENU_TITLE = (
    "🗂 <b>Настройки слов</b>\n"
    "Всё про твой словарь в одном месте 🌸"
)
STUDY_MENU_TITLE = (
    "🔥 <b>Учить сейчас</b>\n"
    "Ручная тренировка — выбери, что повторить. "
    "(Бот и так присылает карточки сам в течение дня 🌙)"
)

# Rewritten for v2. The old help described the course, the TXT import, the
# manual «Учить» mode and a «Новые слова» dial — all hidden or gone — and
# offered to retake a placement test that was deleted. A help screen that names
# buttons which are not there is worse than none: it reads as the bot being
# broken rather than the text being stale.
HELP_TEXT = (
    "❓ <b>Справка — что какая кнопка делает</b>\n\n"
    "📅 <b>Сегодня</b> — план на день: сколько карточек осталось и из чего они. "
    "Карточки приходят сами в течение дня, отвечать можно прямо из чата. Новый "
    "план не появится, пока не закрыт текущий.\n\n"
    "📚 <b>Мой словарь</b> — слова, которые ты учишь, по папкам. Тап на слово → "
    "карточка, оттуда же можно убрать его из обучения. Свои слова добавляются "
    "сообщением: <code>word</code> / <code>word - перевод</code>.\n\n"
    "📦 <b>Коллекции</b> — готовые наборы слов по темам. ✅ — уже в обучении, "
    "⬜ — нет; тап добавляет или убирает.\n\n"
    "🧩 <b>Грамматика</b> — тридцать тем по порядку. Даю фразу по-русски, ты "
    "собираешь её по-английски: сначала из кусочков, потом печатаешь сам. Оценка "
    "у темы от 0 до 5, 🔒 — тема ещё не открыта, до неё дойдёт очередь.\n\n"
    "📊 <b>Прогресс</b> — серия дней подряд, ответы за сегодня, сколько слов "
    "учишь и сколько выучил, покрытие частотного словаря и твой уровень.\n\n"
    "⚙️ <b>Настройки</b>:\n"
    "• ⚡ <b>Темп повторений</b> — как быстро выученное возвращается на проверку\n"
    "• 🔔 <b>Время пушей</b> — окно, когда боту можно слать карточки\n"
    "• 📏 <b>Мой уровень</b> — считается по твоему прогрессу, вручную не задаётся\n"
    "• 🕐 <b>Часовой пояс</b> — чтобы окно и «сегодня» считались по тебе"
)

ADD_WORDS_PROMPT = (
    "✍️ Пришли слово или несколько — каждое с новой строки.\n\n"
    "Форматы:\n"
    "<code>word</code>\n"
    "<code>word - перевод</code>\n"
    "<code>word | пример</code>\n"
    "<code>word - перевод | пример</code>"
)

ADD_CHOOSE_CATEGORY = "📁 Куда сохранить слова?"
ADD_NO_WORDS = "🙈 Не нашёл ни одного подходящего слова. Попробуй ещё раз."
ADD_SUCCESS = "🌱 Добавлено слов: {count}"

TXT_PROMPT = (
    "📂 Пришли .txt файл — каждое слово с новой строки.\n\n"
    "Поддерживаемые форматы:\n"
    "<code>word</code>\n"
    "<code>word - перевод</code>\n"
    "<code>word | пример</code>\n"
    "<code>word - перевод | пример</code>"
)
TXT_TOO_BIG = "😅 Файл великоват. Лимит: {limit_kb} КБ."
TXT_TOO_MANY_LINES = "😅 Слишком много строк. Лимит: {limit}."
TXT_NOT_TEXT = "🤔 Это не .txt. Пришли обычный текстовый файл."
TXT_PARSE_ERROR = "😔 Не получилось разобрать файл. Проверь формат."
TXT_PREVIEW = (
    "🔎 Найдено: <b>{found}</b>\n"
    "Дубликатов: <b>{dups}</b>\n"
    "Будет добавлено: <b>{will}</b>"
)
TXT_IMPORT_DONE = "🌱 Импортировано: {count}"
IMPORT_ASK_PRIORITY = "⚡ Учить их в первую очередь?"
IMPORT_PRIORITY_ON = "⚡ Учить в первую очередь"
IMPORT_PRIORITY_SET = "⚡ Понял — эти слова пойдут вперёд остальных."

QUICK_ADD_PROMPT_ONE = "Добавить «{word}»? 🌱"
QUICK_ADD_PROMPT_MANY = "Добавить эти слова? ({count}) 🌱"
QUICK_ADD_NONE = "🤔 Не похоже на слово. Открой меню → «➕ Добавить»."

CATEGORY_NEW_PROMPT = "✍️ Назови новую категорию (до 64 символов)."
CATEGORY_NEW_TOO_LONG = "😅 Длинновато. До 64 символов."
CATEGORY_NEW_EMPTY = "🙈 Название не может быть пустым."
CATEGORY_NEW_EXISTS = "📁 Категория с таким именем уже есть."
CATEGORY_CREATED = "🌸 Категория «{name}» создана!"

CATEGORY_MANAGE_TITLE = "⚙️ Категория «{name}»\nСлов: {count}"
CATEGORY_RENAME_PROMPT = "✍️ Новое имя категории (до 64 символов)."
CATEGORY_RENAMED = "🌸 Теперь это «{name}»."
CATEGORY_DELETE_CONFIRM = (
    "🗑 Удалить категорию «{name}»?\nСлова не пропадут — переедут в «Без категории»."
)
CATEGORY_DELETED = "🗑 Категория удалена. Слова — в «Без категории»."
CATEGORY_MOVE_PICK = "📦 Куда переместить слова из «{name}»?"
CATEGORY_MERGE_PICK = "🔗 С какой категорией объединить «{name}»?\nСлова переедут туда, а «{name}» удалится."
CATEGORY_MOVED = "🚚 Перемещено слов: {count}"
CATEGORY_MERGED = "🔗 Объединено! Перемещено слов: {count}"
CATEGORY_NO_TARGETS = "🤷 Других категорий нет. Сначала создай ещё одну."
CATEGORY_UNCATEGORIZED = "📁 Без категории"

MY_WORDS_EMPTY = "🌱 Пока пусто. Добавь первые слова через «➕ Добавить»."
MY_WORDS_TITLE = "📁 {category}\nСлов: {count}"
WORD_DETAIL = "<b>{writing}</b>\n🔤 {translation}\n\n💡 {example}"

STUDY_NO_WORDS = "🌸 На сегодня всё! Добавь слов или загляни в «📦 Паки»."
STUDY_FINISHED = (
    "🎉 Сессия завершена!\n\n"
    "✅ Освоено: {learned} из {total}\n"
    "❌ Ошибок: {mistakes}"
)
STUDY_QUIZ_PROMPT = "Выбери перевод 👇"
STUDY_TYPE_PROMPT = "✍️ Напиши по-английски:"
STUDY_ANSWER_CORRECT = "✅ Верно! 🎉"
STUDY_ANSWER_WRONG = "❌ Мимо. Правильно: {answer}"
STUDY_ANSWER_ALMOST = "✅ Почти! Правильно: {answer}\n💡 {hint}"
STUDY_ANSWER_WRONG_HINT = "❌ Мимо. Правильно: {answer}\n💡 {hint}"
STUDY_ANSWER_DEGRADED = (
    "❌ Мимо. Правильно: {answer}\n"
    "⚠️ Умная проверка недоступна — засчитываю строго."
)
# Sent after a re-grade: the checker was down, the answer was scored strictly,
# and the credit has now been applied after the fact.
REGRADE_NOTICE = (
    "🔄 Умная проверка снова на связи — пересмотрел ответы, "
    "которые засчитал строго.\n\n"
    "Теперь засчитано:\n{lines}"
)
# Sent when the recheck ran and changed nothing. The card promised «вернётся
# сама, ответ пересчитаю» — staying silent because the answer really was a miss
# leaves the user waiting on a promise they were never told was kept.
REGRADE_NOTHING = (
    "🔄 Умная проверка снова на связи — перепроверил ответы, "
    "которые засчитал строго.\n\n"
    "Всё сошлось, менять нечего 🌿"
)
STUDY_USE_BUTTONS = "👆 Выбери вариант кнопкой"
STUDY_CARD_NO_TRANSLATION = "(перевода нет)"
STUDY_EXAMPLE_MISSING = "Примера пока нет 🤷"

DELETE_CONFIRM = "🗑 Удалить слово «{word}»?"
DELETED = "🗑 Слово удалено."

CONFLICT_STATE = "🙏 Сначала заверши текущее действие или нажми «Отмена»."
STALE_CALLBACK = "⌛ Это действие уже устарело."
LIST_EXPIRED = "⌛ Список устарел — открой раздел заново 🌸"
ONBOARDING_EXPIRED = "⌛ Сессия истекла — нажми /start, чтобы начать заново."
NON_TEXT_HINT = "🙂 Я понимаю только текст. Напиши слово или воспользуйся меню внизу 👇"
GENERIC_ERROR = "😔 Что-то пошло не так. Попробуй ещё раз."

# Backlog relief — offered when the active pool has outgrown its owner.
BACKLOG_OFFER = (
    "🧹 <b>В работе слишком много слов</b>\n\n"
    "Сейчас {active}, а по твоему темпу комфортно около {target}. "
    "Из-за этого каждое слово возвращается редко и не успевает закрепиться, "
    "а новые не приходят вовсе — пока не разгребёшь.\n\n"
    "Могу отложить {count} слов, по которым меньше всего продвижения. "
    "Не пропадут: вернутся через месяц, а достать раньше можно "
    "в «Архив и отложенные»."
)
BACKLOG_BUTTON = "🧹 Отложить лишние ({count})"
BACKLOG_DONE = (
    "🧹 Отложил {count}. В работе осталось {left}.\n\n"
    "Теперь слова будут возвращаться чаще — и снова начнут приходить новые."
)
BACKLOG_NOTHING = "Сейчас откладывать нечего 🌿"

MANAGED_TITLE = (
    "🗂 <b>Архив и отложенные</b>\n"
    "↩️ — вернуть слово в изучение, ⏰ — показать отложенное сейчас."
)
MANAGED_EMPTY = "🗂 Пусто. Ты пока ничего не убирал и не откладывал 🌸"
MANAGED_RESTORED = "↩️ Вернул в изучение."
MANAGED_UNSNOOZED = "⏰ Снова в показе."

DIGEST_TITLE = "🗞 <b>Итоги недели</b>\n"
DIGEST_ACCURACY = (
    "💬 <b>{answers}</b> {answers_word} за неделю "
    "(🔤 слова: {words} · 📖 грамматика: {grammar})\n"
    "🎯 Точность: <b>{accuracy}%</b>"
)
DIGEST_MASTERED_DELTA = "⭐ Выучено за неделю: <b>+{delta}</b> (всего {total})"
DIGEST_MASTERED = "⭐ Выучено всего: <b>{total}</b>"
DIGEST_STREAK = "🔥 Серия: <b>{streak}</b> {days_word} подряд"
DIGEST_HARDEST = "🥊 Крепкий орешек: <b>{word}</b> — {wrongs} {wrongs_word} за неделю. Дожмём!"
DIGEST_OUTRO = "Так держать! Новая неделя — новые слова 🌱"

REMINDER_STREAK = "🔥 Streak {streak} дн. под угрозой! Позанимайся сегодня — хватит пары минут."
REMINDER_DAILY = "🎯 Сегодня {studied}/{goal}. Закроем цель? Осталось {left}."
REMINDER_INACTIVE = "👋 Давно не виделись. Вернись и повтори слова — даже 5 минут в день работают."

PUSH_CARD = "Что значит <b>{word}</b>?"
PUSH_CARD_REVERSE = "Как сказать по-английски «<b>{translation}</b>»?"
# Typed production for words a cloze can't reach — phrasebook entries, and
# anything still lacking a maskable example. Same question as the reverse card,
# but written out instead of picked from four options.
PUSH_CARD_TYPE_IN = (
    "Напиши по-английски:\n"
    "<b>{translation}</b>\n\n"
    "Ответь сообщением 👇"
)
PUSH_CARD_CLOZE = (
    "Впиши пропущенное слово (<b>{translation}</b>):\n\n"
    "{sentence}\n\n"
    "<i>Ответь сообщением 👇</i>"
)
PUSH_GRAMMAR_CARD = "Выбери верную форму:\n\n{prompt}"
PUSH_RULE_CARD = "📖 <b>{title}</b>\n\n{rule}"
PUSH_RULE_OK = "👍 Поехали — лови упражнения."
PUSH_ANSWER_CORRECT = "✅ Верно! 🎉"
PUSH_ANSWER_WRONG = "❌ Мимо. Правильно: <b>{answer}</b>"
# Near-miss feedback: the check understood WHAT went wrong, so the card says so
# instead of a bare miss.
PUSH_ANSWER_ALMOST = "✅ Почти! Правильно: <b>{answer}</b>\n💡 {hint}"
PUSH_ANSWER_WRONG_HINT = "❌ Мимо. Правильно: <b>{answer}</b>\n💡 {hint}"
# Shown when the check couldn't run. Says the bot got stricter and why, rather
# than letting the user think it suddenly stopped understanding them.
PUSH_ANSWER_DEGRADED = (
    "❌ Мимо. Правильно: <b>{answer}</b>\n"
    "<i>⚠️ Умная проверка сейчас недоступна — засчитываю строго. "
    "Вернётся сама, ответ пересчитаю.</i>"
)
# Post-answer recap. The verdict alone ("✅ Верно!") threw away everything the
# card had shown — which word it even was, and how close it is to being learned.
# Now the answer reveals the pair, and the progress line comes back as a
# before → after so the tap visibly moved something.
# On a hit the word is an anchor, not a lesson: the user just produced this
# pairing themselves, so repeating the translation back tells them nothing.
# The miss is the only place it teaches — there the pair comes out in full.
PUSH_RECAP_WORD = "<b>{writing}</b>"
PUSH_RECAP_TRANSLATION = "↳ {translation}"
PUSH_RECAP_EXAMPLE = "📝 <i>{sentence}</i>"
PUSH_RECAP_MASTERED_NOW = "⭐ Слово выучено! Дальше — редкие повторы для поддержки."
PUSH_RECAP_MASTERED = "⭐ Выучено на {score} из 5"
PUSH_RECAP_PROGRESS = "🌱 {before}% → {after}%"
PUSH_RECAP_PROGRESS_FLAT = "🌱 {after}%"
PUSH_RECAP_TYPED_LEFT = "✍️ напечатать ещё {n} {times}"
PUSH_RECAP_NEXT = "🔁 вернусь {when}"

PUSH_STALE = "⌛ Эта карточка уже неактуальна."
PUSH_HIDDEN = "🙈 Больше не показываю это слово."
PUSH_MASTERED_KNOWN = "✅ Отметил как выученное — буду лишь изредка повторять."
PUSH_SNOOZED = "😴 Отложил на {label}."
PUSH_LEECH_PROMPT = (
    "🥵 Слово <b>{word}</b> даётся тяжело — уже 6 ошибок подряд.\n"
    "Отложить его на недельку? Прогресс сохранится, потом вернётся само."
)
PUSH_LEECH_PARKED = "😴 Отложил на неделю. Вернётся, когда отдохнёшь от него."
PUSH_LEECH_KEPT = "💪 Ок, оставляем — дожмём."
PUSH_PACE_TITLE = (
    "🚀 <b>Темп — сколько новых слов в день</b>\n\n"
    "Это скорость, с которой бот добавляет <b>новые</b> слова в обучение. "
    "Старые при этом никуда не деваются — их продолжаем повторять.\n\n"
    "Сейчас: <b>{current}</b>\n\n"
    "🐢 Спокойно — 3 в день\n"
    "🚶 Ровно — 7 в день\n"
    "🏃 Бодро — 15 в день\n"
    "🔥 Жёстко — 25 в день\n\n"
    "<i>Чем выше темп, тем больше повторений накопится через пару недель — "
    "выбирай по силам.</i>"
)
PUSH_PACE_SET = "🚀 Темп: {label}."
# Named for what it holds. «Пуш-обучение» described a mode you could configure
# back when there was something to configure; all that is left behind this entry
# is the window, and a title promising more sends the learner looking for it.
PUSH_TITLE = (
    "🔔 <b>Время пушей</b>\n"
    "Карточки приходят сами в течение дня — это основной режим, он всегда включён.\n"
    "Настроить можно одно: когда тебя можно беспокоить 🌙"
)
# The minimum is a setting, so these take it as an argument rather than naming
# a number that quietly stops being true the moment the setting changes.
PUSH_WINDOW_TITLE = (
    "🕐 <b>Окно пушей</b> — когда боту можно слать карточки.\n"
    "Сначала час начала, потом час конца. Можно через ночь "
    "(например 22→08), но не меньше {min_hours} ч 🌙"
)
PUSH_WINDOW_PENDING = "🌅 {ws:02d}:00 → 🌙 {we:02d}:00  ·  {hours} ч"
PUSH_WINDOW_TOO_SHORT = "🙅 Окно должно быть не меньше {min_hours} ч."

# The daily goal is gone from here because nothing in the menu can change it:
# the dial was removed when the day plan took over sizing the day, and the
# stored number now only feeds the reminder worker. A figure shown but not
# settable reads as a control the learner has lost, not as information.
SETTINGS_TITLE = (
    "⚙️ <b>Настройки</b> 🌸\n"
    "Трек: {track}\n\n"
    "⚡ Темп повторений: <b>{pace}</b>"
)
SETTINGS_GOAL_PROMPT = "🎯 Новая дневная цель (1–100):"
SETTINGS_GOAL_UPDATED = "🌸 Цель: {goal} слов в день"
TZ_TITLE = (
    "🕐 <b>Часовой пояс</b>\n"
    "Сейчас: <b>{tz}</b>\n"
    "Выбери свой — окно пушей и «сегодня/streak» будут по твоему времени."
)

PACE_LABELS = {
    "chill": "🐢 Chill",
    "normal": "⚡ Normal",
    "intensive": "🔥 Intensive",
    "hardcore": "💀 Hardcore",
}

# The old copy described two things that no longer exist: how many new words a
# manual «Учить» session hands out (that mode is hidden) and a daily goal that
# set the push speed (the day plan does). What the setting actually does is
# multiply the review interval — PACE_INTERVAL_MULTIPLIER, applied on every
# answer — so the text says that and nothing else.
PACE_TITLE = (
    "⚡ <b>Темп повторений</b>\n"
    "Как быстро выученное слово возвращается на проверку:\n\n"
    "🐢 <b>Chill</b> — спокойно, слова возвращаются реже\n"
    "⚡ <b>Normal</b> — обычный ритм\n"
    "🔥 <b>Intensive</b> — повторы чаще\n"
    "💀 <b>Hardcore</b> — повторы вдвое чаще обычного\n\n"
    "💡 На размер плана не влияет — его бот считает сам."
)

COURSE_INTRO = (
    "🎓 <b>Курс</b>\n\n"
    "Я сам поведу тебя по уровням <b>A1 → B2</b>: карточки приходят в течение дня, "
    "только выбор — ничего не нужно искать или печатать. Выучил слово — подкидываю "
    "следующее. 🌸\n\nНачнём?"
)
COURSE_STARTED = "🚀 Поехали! Карточки начнут приходить в течение дня. Можно и сразу размяться — «🔥 Учить»."
COURSE_PROGRESS = (
    "🎓 <b>Курс</b> · уровень <b>{level}</b>\n"
    "Урок <b>{lesson}/{total_lessons}</b>\n"
    "{bar} {mastered}/{total} слов выучено\n"
    "📚 Сейчас в работе: {in_progress}"
)
COURSE_FINISHED = "🎉 Курс пройден — все {total} слов выучены! Теперь повторяю их, чтобы не забывались."
COURSE_PAUSED = "⏸ Курс на паузе. Новые слова больше не подкидываю — но повторение продолжается. Включить можно тут же."
COURSE_MAP_TITLE = (
    "🗺 <b>Карта курса</b>\n"
    "Урок <b>{lesson}</b> из {total_lessons} · сейчас уровень <b>{level}</b>\n"
)
COURSE_MAP_TITLE_FINISHED = "🗺 <b>Карта курса</b>\n🎉 Курс пройден целиком!\n"

SEARCH_PROMPT = (
    "🔎 <b>Поиск</b>\n\n"
    "Напиши слово или перевод — поищу и в твоём словаре, и в каталоге.\n"
    "<i>Например: forget или «забывать»</i>"
)
SEARCH_RESULTS = (
    "🔎 По запросу «<b>{query}</b>»:\n"
    "📗 в твоём словаре: {own} · ➕ можно добавить: {catalog}\n\n"
    "<i>Можно сразу написать новый запрос 👇</i>"
)
SEARCH_EMPTY = (
    "🔎 По запросу «<b>{query}</b>» ничего не нашлось 🤷\n\n"
    "Попробуй иначе — или напиши «{query} — перевод», и я добавлю это как новое слово."
)
SEARCH_ADDED = "🌱 Добавил в «Мои слова»!"

PACKS_GROUPS_TITLE = "📦 Паки — выбери раздел 🌸"
PACKS_TITLE = (
    "📦 Паки\n"
    "Отметь нужные и жми «Добавить выбранные». "
    "Каждый пак станет папкой в «📚 Мои слова» 🌸"
)
PACKS_ADDED_SUMMARY = "🌱 Добавлено: {added} новых слов из {packs} паков!"
PACKS_NONE_SELECTED = "🤷 Ничего не выбрано."
PACK_TOGGLE_ADDED = "🌱 Добавлено: {count} слов"
PACK_TOGGLE_NONE_NEW = "👌 Все слова этого пака уже у тебя"
PACK_REMOVE_CONFIRM = "🗑 Убрать пак «{title}»?\n{count} слов уйдут из обучения, прогресс по ним сотрётся."
PACK_REMOVED = "🗑 Убрано слов: {count}"
PACK_COURSE_MANAGED = "🎓 Уровни ведёт курс — управляй ими в «🎓 Курс»."

PACKS_PICK_CATEGORIES = "Выбери категории паков:"
PACKS_LIST_TITLE = "Доступные паки"
PACK_PREVIEW = "<b>{title}</b>\n{description}\n\nСлов: {count}"
PACK_ADDED = "🌱 Пак добавлен: {count} новых слов."
PACK_ALREADY_ADDED = "👌 Все слова из этого пака уже у тебя есть."

# Batch triage — the button that closes the screen. Named rather than inline so
# the label stays identical between the first render and every toggle redraw;
# a changing button text makes the keyboard look like it reset.
TRIAGE_DONE = "Готово"
