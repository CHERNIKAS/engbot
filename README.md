# EnglshBot

Telegram-бот для изучения английских слов с интервальным повторением, личным словарём и тематическими паками. Без Mini App, без платных AI API, весь UX — через inline-кнопки.

## Стек

- Python 3.12+
- aiogram 3.x
- PostgreSQL 16 (asyncpg + SQLAlchemy 2 async)
- Redis 7 (FSM, screen versions, rate-limit, study cache)
- Alembic для миграций
- Docker compose для локального запуска

## Быстрый старт (Docker)

```bash
cp .env.example .env
# В .env пропиши BOT_TOKEN от @BotFather

docker compose up --build
```

Compose сам прогонит миграции и запустит бот.

## Локальный запуск

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Запусти Postgres и Redis локально или через:
docker compose up -d postgres redis

cp .env.example .env
# Замени BOT_TOKEN

alembic upgrade head
python -m app.main
```

## Тесты

```bash
pip install -e ".[dev]"
pytest -q
```

Покрытие smoke-тестами:

- `tests/test_word_parser.py` — парсинг ручного ввода и TXT.
- `tests/test_repetition.py` — SM-2-подобный алгоритм SR.
- `tests/test_interaction_state.py` — Redis-FSM поведение.
- `tests/test_example_provider.py` — локальный ExampleProvider.

## Архитектура

См. [PLAN.md](PLAN.md) — структура проекта, схема БД, state machine, callback-схема, user flows.

## Доступ по паролю

Бот закрыт паролем. Значение задаётся через `ACCESS_PASSWORD` в `.env` (по умолчанию `208197`). Пустая строка отключает гейт. При первом `/start` бот просит пароль; правильный ответ помечает пользователя как `is_authorized=true` и пускает в онбординг. Любые сообщения/кнопки до авторизации отклоняются.

## Multi-track архитектура

Бот поддерживает несколько learning tracks: 🇺🇸 English и 🇯🇵 Japanese. В онбординге пользователь выбирает один или оба. У каждого трека своя дневная цель, темп, словарь, категории, паки, study sessions, расписание повторений, статистика. **Глобальный streak** — общий по всем трекам.

- `users.is_authorized` — gate.
- `user_tracks(user_id, track, daily_goal_words, learning_pace, is_active, onboarding_completed, settings JSONB)` — per-track настройки (например `settings.romaji_enabled`).
- `words.track`, `categories.track`, `packs.track`, `user_words.track`, `study_sessions.track`, `word_reviews.track` — изоляция по треку.
- Текущий трек хранится в Redis (`current_track:{user_id}`), переключается из главного меню.

В MVP сейчас залит только English-контент (5 паков, локальные примеры). Японские паки и Japanese-specific онбординг (Hiragana → Katakana → Words → Kanji), Japanese-карточки с раскрытием kana/romaji/translation, тоггл романджи — оставлены под отдельный этап. Foundation уже не привязана к английскому.

## Что есть в MVP

- Парольный гейт.
- Онбординг: выбор треков (English / Japanese / оба) + дневная цель (1–100).
- Главное меню: «Мои слова», «Учить», «Добавить», «Импорт TXT», «Паки», «Прогресс», «Настройки».
- Ручное добавление слов в форматах: `word`, `word - перевод`, `word | пример`, `word - перевод | пример`.
- Quick Add Popup для текста, отправленного в idle.
- Импорт TXT с превью и проверкой лимитов (размер, число строк, число слов).
- Личные категории + добавление в категорию из любого флоу.
- Готовые тематические паки (Crypto, IT, Business, Travel, Basic English).
- Режимы обучения: Classic Cards (показать перевод → Сложно/Нормально/Легко), Quiz, Skip, удаление слова прямо в карточке.
- Spaced repetition с настраиваемым learning pace (Chill / Normal / Intensive / Hardcore).
- Прогресс: streak, цель на сегодня, всего слов, выучено, слабые слова.
- Локальный ExampleProvider (JSON) — расширяется без изменения сервиса.

## Что НЕ делается (по ТЗ)

Telegram Mini App, платные AI API, public decks, listening mode, shadow learning, voice, web scraping, paywalls, командный UX.

## Полезные команды

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "your message"

# Применить миграции
alembic upgrade head

# Откатить
alembic downgrade -1
```

## Структура

```
app/
  bot/             # Telegram-слой (handlers, keyboards, middlewares, callbacks, states)
  domain/          # ORM-модели и доменные enum'ы
  infrastructure/  # БД, Redis, репозитории, ExampleProvider
  services/        # Доменные сервисы (тонкая бизнес-логика)
  config.py        # Pydantic settings
  main.py          # Точка входа
migrations/        # Alembic
tests/             # pytest
```

## Расширение

- **ExampleProvider**: реализуй протокол `app.infrastructure.example_provider.base.ExampleProvider` (например, Tatoeba dump, открытый словарь, в будущем — AI) и подмени в `main.py`.
- **Новые паки**: добавь миграцию, аналогичную `0002_seed_packs.py`.
- **Локализация**: вынесено в `app/bot/texts.py` — добавить второй язык можно одним словарём.
