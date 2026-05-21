from __future__ import annotations

# Russian text constants — kept centralised so we can localise later.

PASSWORD_PROMPT = "Доступ ограничен. Введи пароль."
PASSWORD_WRONG = "Неверный пароль. Попробуй ещё раз."
PASSWORD_OK = "Пароль принят."
PASSWORD_REQUIRED_HINT = "Доступ закрыт. Отправь /start и введи пароль."

INTRO = (
    "<b>Lazy Bot</b> — твой персональный словарь и тренажёр английских слов.\n\n"
    "Добавляй слова, импортируй TXT, выбирай тематические паки и учи через "
    "интервальное повторение."
)

ASK_TRACKS = "Что хочешь учить?"
ASK_DAILY_GOAL = "Сколько слов в день хочешь учить?"
ASK_CUSTOM_GOAL = "Введи число от 1 до 100."
ERROR_GOAL_TOO_SMALL = "Слишком мало. Выбери число от 1 до 100."
ERROR_GOAL_TOO_BIG = "Слишком много для нормального обучения. Выбери число от 1 до 100."
ERROR_GOAL_NOT_NUMBER = "Это не похоже на число. Введи целое число от 1 до 100."

ONBOARDING_DONE = "Готово! Бот настроен."

MAIN_MENU = "Главное меню"

ADD_WORDS_PROMPT = (
    "Отправь слово или несколько слов. Можно каждое с новой строки.\n\n"
    "Форматы:\n"
    "<code>word</code>\n"
    "<code>word - перевод</code>\n"
    "<code>word | пример</code>\n"
    "<code>word - перевод | пример</code>"
)

ADD_CHOOSE_CATEGORY = "Куда сохранить слова?"
ADD_NO_WORDS = "Не нашёл ни одного валидного слова. Попробуй ещё раз."
ADD_SUCCESS = "✅ Добавлено: {count} слов"

TXT_PROMPT = (
    "Отправь .txt файл. Каждое слово с новой строки.\n\n"
    "Поддерживаемые форматы:\n"
    "<code>word</code>\n"
    "<code>word - перевод</code>\n"
    "<code>word | пример</code>\n"
    "<code>word - перевод | пример</code>"
)
TXT_TOO_BIG = "Файл слишком большой. Лимит: {limit_kb} КБ."
TXT_TOO_MANY_LINES = "Слишком много строк. Лимит: {limit} строк."
TXT_NOT_TEXT = "Это не .txt файл. Отправь обычный текстовый файл."
TXT_PARSE_ERROR = "Не получилось обработать файл. Проверь формат."
TXT_PREVIEW = (
    "Найдено: <b>{found}</b> слов\n"
    "Дубликатов: <b>{dups}</b>\n"
    "Будет добавлено: <b>{will}</b>"
)
TXT_IMPORT_DONE = "✅ Импортировано: {count} слов"

QUICK_ADD_PROMPT_ONE = "Добавить «{word}»?"
QUICK_ADD_PROMPT_MANY = "Добавить эти слова? ({count})"
QUICK_ADD_NONE = "Не похоже на слово. Открой меню и нажми «➕ Добавить»."

CATEGORY_NEW_PROMPT = "Введи название новой категории (до 64 символов)."
CATEGORY_NEW_TOO_LONG = "Слишком длинно. До 64 символов."
CATEGORY_NEW_EMPTY = "Название не может быть пустым."
CATEGORY_NEW_EXISTS = "Категория с таким именем уже есть."
CATEGORY_CREATED = "✅ Категория «{name}» создана."

MY_WORDS_EMPTY = "Пока нет слов. Добавь первые через «➕ Добавить»."
MY_WORDS_TITLE = "📁 {category}\nСлов: {count}"

STUDY_NO_WORDS = "Сегодня нечего учить. Добавь слов или загляни в «📦 Паки»."
STUDY_FINISHED = (
    "✅ Сессия завершена\n\n"
    "Верно: {correct}\n"
    "Ошибки: {wrong}\n"
    "Всего: {total}"
)
STUDY_CARD_NO_TRANSLATION = "(перевода нет)"
STUDY_EXAMPLE_MISSING = "Для этого слова пока нет примера."

DELETE_CONFIRM = "Удалить слово «{word}»?"
DELETED = "Слово удалено."

CONFLICT_STATE = "Сначала заверши текущее действие или нажми «Отмена»."
STALE_CALLBACK = "Это действие уже устарело."
GENERIC_ERROR = "Что-то пошло не так. Попробуй ещё раз."

PROGRESS_TITLE = (
    "🔥 Streak: <b>{streak}</b> дней\n\n"
    "{per_track}"
)

SETTINGS_TITLE = (
    "⚙️ <b>Настройки</b>\n"
    "Трек: {track}\n\n"
    "🎯 Цель в день: <b>{goal}</b>\n"
    "⚡ Темп: <b>{pace}</b>"
)
SETTINGS_GOAL_PROMPT = "Введи новую дневную цель (1–100)."
SETTINGS_GOAL_UPDATED = "Цель обновлена: {goal} слов в день."

PACE_LABELS = {
    "chill": "🐢 Chill",
    "normal": "⚡ Normal",
    "intensive": "🔥 Intensive",
    "hardcore": "💀 Hardcore",
}

PACKS_PICK_CATEGORIES = "Выбери категории паков:"
PACKS_LIST_TITLE = "Доступные паки"
PACK_PREVIEW = "<b>{title}</b>\n{description}\n\nСлов: {count}"
PACK_ADDED = "✅ Пак добавлен: {count} новых слов."
PACK_ALREADY_ADDED = "Все слова из этого пака уже у тебя есть."
