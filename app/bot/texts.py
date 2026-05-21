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

MAIN_MENU = "Главное меню 🌸"

# Persistent bottom reply-keyboard buttons (main navigation).
BTN_MY_WORDS = "📚 Мои слова"
BTN_STUDY = "🔥 Учить"
BTN_ADD = "➕ Добавить слова"
BTN_IMPORT = "📂 Импорт TXT"
BTN_PACKS = "📦 Паки"
BTN_PROGRESS = "📊 Прогресс"
BTN_SETTINGS = "⚙️ Настройки"
MENU_BUTTON_TEXTS: frozenset[str] = frozenset(
    {BTN_MY_WORDS, BTN_STUDY, BTN_ADD, BTN_IMPORT, BTN_PACKS, BTN_PROGRESS, BTN_SETTINGS}
)
MENU_PLACEHOLDER = "Выбери действие 🌸"

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
STUDY_USE_BUTTONS = "👆 Выбери вариант кнопкой"
STUDY_CARD_NO_TRANSLATION = "(перевода нет)"
STUDY_EXAMPLE_MISSING = "Примера пока нет 🤷"

DELETE_CONFIRM = "🗑 Удалить слово «{word}»?"
DELETED = "🗑 Слово удалено."

CONFLICT_STATE = "🙏 Сначала заверши текущее действие или нажми «Отмена»."
STALE_CALLBACK = "⌛ Это действие уже устарело."
GENERIC_ERROR = "😔 Что-то пошло не так. Попробуй ещё раз."

PROGRESS_TITLE = (
    "🌸 <b>Твой прогресс</b>\n"
    "🔥 Streak: <b>{streak}</b> дн.\n\n"
    "{per_track}"
)

REMINDER_STREAK = "🔥 Streak {streak} дн. под угрозой! Позанимайся сегодня — хватит пары минут."
REMINDER_DAILY = "🎯 Сегодня {studied}/{goal}. Закроем цель? Осталось {left}."
REMINDER_INACTIVE = "👋 Давно не виделись. Вернись и повтори слова — даже 5 минут в день работают."

PUSH_CARD = "🔔 Что значит <b>{word}</b>?"
PUSH_ANSWER_CORRECT = "✅ Верно! 🎉"
PUSH_ANSWER_WRONG = "❌ Мимо. Правильно: <b>{answer}</b>"
PUSH_STALE = "⌛ Эта карточка уже неактуальна."
PUSH_SCHEDULE_PROMPT = "🔔 График пушей: <b>{ws:02d}:00–{we:02d}:00</b>. Оставить или поменять?"
PUSH_SCHEDULE_KEPT = "👌 Ок, график прежний."
PUSH_TITLE = (
    "🔔 <b>Пуш-обучение</b>\n"
    "Бот сам присылает карточки в течение дня — это основной режим, он всегда включён.\n"
    "Настрой только окно: когда можно беспокоить 🌙"
)
PUSH_WINDOW_TITLE = "🕐 Окно пушей (минимум 10 ч).\nВерхний ряд — начало дня, нижний — конец."
PUSH_WINDOW_TOO_SHORT = "🙅 Окно должно быть не меньше 10 часов."

SETTINGS_TITLE = (
    "⚙️ <b>Настройки</b> 🌸\n"
    "Трек: {track}\n\n"
    "🎯 Цель в день: <b>{goal}</b>\n"
    "⚡ Темп: <b>{pace}</b>"
)
SETTINGS_GOAL_PROMPT = "🎯 Новая дневная цель (1–100):"
SETTINGS_GOAL_UPDATED = "🌸 Цель: {goal} слов в день"

PACE_LABELS = {
    "chill": "🐢 Chill",
    "normal": "⚡ Normal",
    "intensive": "🔥 Intensive",
    "hardcore": "💀 Hardcore",
}

PACKS_TITLE = (
    "📦 Паки\n"
    "Отметь нужные и жми «Добавить выбранные». "
    "Каждый пак станет папкой в «📚 Мои слова» 🌸"
)
PACKS_ADDED_SUMMARY = "🌱 Добавлено: {added} новых слов из {packs} паков!"
PACKS_NONE_SELECTED = "🤷 Ничего не выбрано."

PACKS_PICK_CATEGORIES = "Выбери категории паков:"
PACKS_LIST_TITLE = "Доступные паки"
PACK_PREVIEW = "<b>{title}</b>\n{description}\n\nСлов: {count}"
PACK_ADDED = "🌱 Пак добавлен: {count} новых слов."
PACK_ALREADY_ADDED = "👌 Все слова из этого пака уже у тебя есть."
