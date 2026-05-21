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
MENU_PLACEHOLDER = "Выберите действие…"

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

CATEGORY_MANAGE_TITLE = "⚙️ Управление категорией «{name}»\nСлов: {count}"
CATEGORY_RENAME_PROMPT = "Введи новое имя категории (до 64 символов)."
CATEGORY_RENAMED = "✅ Переименовано в «{name}»."
CATEGORY_DELETE_CONFIRM = (
    "Удалить категорию «{name}»?\nСлова не пропадут — станут «Без категории»."
)
CATEGORY_DELETED = "🗑 Категория удалена. Слова перемещены в «Без категории»."
CATEGORY_MOVE_PICK = "Куда переместить слова из «{name}»?"
CATEGORY_MERGE_PICK = "С какой категорией объединить «{name}»?\nСлова переедут туда, а «{name}» удалится."
CATEGORY_MOVED = "✅ Перемещено слов: {count}."
CATEGORY_MERGED = "✅ Объединено. Перемещено слов: {count}."
CATEGORY_NO_TARGETS = "Нет других категорий. Сначала создай ещё одну."
CATEGORY_UNCATEGORIZED = "📁 Без категории"

MY_WORDS_EMPTY = "Пока нет слов. Добавь первые через «➕ Добавить»."
MY_WORDS_TITLE = "📁 {category}\nСлов: {count}"

STUDY_NO_WORDS = "Сегодня нечего учить. Добавь слов или загляни в «📦 Паки»."
STUDY_FINISHED = (
    "✅ Сессия завершена\n\n"
    "Освоено: {learned} из {total}\n"
    "Ошибок: {mistakes}"
)
STUDY_QUIZ_PROMPT = "Выбери перевод:"
STUDY_TYPE_PROMPT = "✍️ Напиши по-английски:"
STUDY_ANSWER_CORRECT = "✅ Верно!"
STUDY_ANSWER_WRONG = "❌ Неверно. Правильно: {answer}"
STUDY_USE_BUTTONS = "Выбери вариант кнопкой 👆"
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

PACKS_TITLE = (
    "📦 Паки\n"
    "Отметь нужные и нажми «Добавить выбранные». "
    "Каждый пак станет папкой в «📚 Мои слова»."
)
PACKS_ADDED_SUMMARY = "✅ Добавлено: {added} новых слов из {packs} паков."
PACKS_NONE_SELECTED = "Ничего не выбрано."

PACKS_PICK_CATEGORIES = "Выбери категории паков:"
PACKS_LIST_TITLE = "Доступные паки"
PACK_PREVIEW = "<b>{title}</b>\n{description}\n\nСлов: {count}"
PACK_ADDED = "✅ Пак добавлен: {count} новых слов."
PACK_ALREADY_ADDED = "Все слова из этого пака уже у тебя есть."
