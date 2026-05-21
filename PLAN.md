# EnglshBot — MVP Plan

## 1. Stack

- Python 3.12+
- aiogram 3.x (async Telegram framework)
- PostgreSQL 16 (asyncpg + SQLAlchemy 2 async ORM)
- Redis 7 (FSM, rate-limiting, screen versions, ephemeral UI state)
- Alembic (migrations)
- Docker + docker-compose for local dev
- pytest + pytest-asyncio for tests

## 2. Project layout

```
app/
  bot/
    handlers/        # thin Telegram handlers
      onboarding.py
      main_menu.py
      my_words.py
      add_words.py
      txt_import.py
      categories.py
      packs.py
      study.py
      progress.py
      settings.py
      fallback.py    # quick-add + stale callback handler
    keyboards/       # InlineKeyboardMarkup builders
      common.py
      onboarding.py
      main_menu.py
      my_words.py
      study.py
      packs.py
      settings.py
    middlewares/
      db.py          # injects async session into handler
      interaction_guard.py
      rate_limit.py
      user_loader.py
    callbacks/
      schema.py      # CallbackData factories (aiogram CallbackData)
    texts.py         # i18n-ready string constants (RU default)
    states.py        # InteractionState enum
  domain/
    models.py        # SQLAlchemy ORM models
    enums.py
  infrastructure/
    db/
      engine.py
      session.py
      base.py
    redis_client.py
    repositories/
      users.py
      words.py
      user_words.py
      categories.py
      packs.py
      sessions.py
      reviews.py
    example_provider/
      base.py        # ExampleProvider protocol
      local_json.py  # default LocalJsonExampleProvider
      data/examples.json
  services/
    user_service.py
    word_parser.py
    word_import_service.py
    category_service.py
    pack_service.py
    repetition_service.py
    study_session_service.py
    progress_service.py
    interaction_state_service.py
    analytics.py
  config.py
  logging_setup.py
  main.py
migrations/          # Alembic
tests/
  test_word_parser.py
  test_repetition.py
  test_interaction_state.py
  test_import_service.py
docker-compose.yml
Dockerfile
pyproject.toml
.env.example
README.md
PLAN.md
```

## 3. Database schema (key points)

Tables: `users`, `categories`, `words`, `user_words`, `packs`, `pack_words`, `study_sessions`, `word_reviews`, `analytics_events`.

Key constraints/indexes:
- `users.telegram_id` UNIQUE.
- `words.normalized_word` UNIQUE (canonical lowercase form).
- `categories(user_id, name)` UNIQUE for user-owned categories.
- `user_words(user_id, word_id, category_id)` UNIQUE composite — prevents duplicate same-word-in-same-category. NULL category_id treated via `COALESCE` or via a partial index pair.
- Indexes on `user_words(user_id, next_review_at)` and `user_words(user_id, status)` for fast study queries.
- `word_reviews(user_word_id, reviewed_at DESC)`.
- All FKs `ON DELETE CASCADE` for user-owned data.

## 4. Interaction state machine

Single `InteractionState` enum stored per user in Redis at `state:{user_id}` with TTL (default 15 min, study session 60 min):
- `idle`
- `onboarding_daily_goal`
- `onboarding_custom_goal`
- `waiting_manual_words`
- `waiting_category_for_words`
- `waiting_new_category_name`
- `waiting_txt_file`
- `waiting_txt_category`
- `waiting_delete_confirmation`
- `study_active`
- `pack_selection`
- `settings_goal_input`
- `settings_pace_input`

`InteractionStateService` API:
- `get(user_id) -> StatePayload`
- `set(user_id, state, payload, ttl)`
- `clear(user_id)`
- `transition(user_id, expected_from, to, payload)`
- `assert_in(user_id, allowed: set[State])`

`InteractionGuard` middleware:
- Resolves user from update.
- Looks up current state.
- Whitelists callbacks/messages by state (mapping `state -> {allowed_callback_prefixes, allowed_message_kinds}`).
- Universal escapes: `cancel`, `back`, `/start`, "main menu" callback always allowed (cancel clears state).
- On conflict: `answerCallbackQuery("Сначала заверши текущее действие или нажми Отмена.")` and stop propagation.

## 5. Callback schema

Use aiogram `CallbackData` factories. Top-level prefixes:
- `mm:` main menu
- `ob:` onboarding
- `mw:` my words list
- `cat:` categories
- `add:` add words flow
- `imp:` txt import
- `pk:` packs
- `st:` study session
- `pg:` progress
- `set:` settings
- `del:` delete confirm
- `nav:` shared (back/cancel/home)
- `noop:` placeholder

Every callback that mutates state-bound UI carries a `v` (screen version) field. The server stores `screen:{user_id}:{kind}` in Redis. Mismatch → "Это действие уже устарело." Plus answerCallbackQuery.

## 6. Spaced repetition (simple SM-2 variant)

Per `user_word`:
- `status`: new / learning / review / mastered
- `ease_score` float (start 2.5, clamp 1.3–3.0)
- `repetitions_count` int
- `mistakes_count` int
- `interval_days` float
- `next_review_at` datetime

Algorithm on answer:
- `easy`: ease += 0.15; interval = max(interval*ease, 4); reps++; if reps>=4 and ease>=2.6 → mastered.
- `normal`: ease unchanged; interval = max(interval*ease, 1) with reps++; if reps>=6 → mastered.
- `hard`: ease -= 0.2 (floor 1.3); interval = max(interval*0.5, 0.5); mistakes++; status stays/back to learning.
- `wrong`/quiz incorrect: ease -= 0.25; interval = 0.25 (≈6 hrs); reps=0; status=learning; mistakes++.
- `correct` (quiz): treated like normal.

Pace modifiers applied to the resulting interval:
- chill ×1.3 / normal ×1.0 / intensive ×0.8 / hardcore ×0.6
- New-words-per-session: chill 3 / normal 6 / intensive 10 / hardcore 15.

## 7. Study session lifecycle

`StudySessionService.start(user_id, mode, scope)`:
- mode ∈ {classic, quiz, typing}
- scope ∈ {goal, all, category(id), weak, new, quick}
- Selects up to `daily_goal - studied_today` words for `goal` mode, or N for `quick`.
- Word selection query (single SQL):
  - Due reviews first (`next_review_at <= now`), ordered by `next_review_at`.
  - Then new words, capped by pace.
  - Optional category filter.
- Session stored as DB row + Redis cache `session:{user_id}` for in-progress state (current_index, words[], answers[], started_at).

On each answer:
- Update Redis snapshot.
- Persist `word_reviews` row.
- Update `user_words` via RepetitionService.
- Update `study_sessions.correct_count / wrong_count`.

On finish (all words done OR user exits):
- Mark session finished, update streak via ProgressService.

## 8. Word parser

Single tolerant parser handles all manual + TXT input.
Supported formats per line:
- `word`
- `word - translation`
- `word — translation`
- `word | example`
- `word - translation | example`
- `word = translation` (also accept)
- BOM-stripped, whitespace-trimmed, blank lines skipped, deduped (case-insensitive on normalized form), comments starting with `#` skipped.
- Limits: per call ≤ 5000 raw lines parsed, ≤ 1000 valid words committed.

## 9. Example provider

Protocol:
```python
class ExampleProvider(Protocol):
    async def get_example(self, normalized_word: str) -> str | None
```

Default `LocalJsonExampleProvider` loads `app/infrastructure/example_provider/data/examples.json` (seeded with a few hundred common-word examples — we can extend by dumping Tatoeba subsets later). Returns None if not found. Easy to swap later.

## 10. Quick Add Popup

In `idle` state, any plain text message that parses to ≥1 valid word triggers a popup with:
- ✅ Добавить (uses default category = "Без категории")
- 📁 Выбрать категорию
- ❌ Отмена

Stored as ephemeral payload `quickadd:{user_id}` in Redis (TTL 5 min) so callback survives without bloated callback_data.

## 11. Analytics hooks

`analytics.emit(event_name, user_id, **props)` writes to `analytics_events` table. No external sink yet.

Events: `onboarding_completed`, `word_added`, `txt_imported`, `study_started`, `study_completed`, `streak_updated`, `pack_added`.

## 12. User flows (happy paths)

1. **First start** → onboarding intro → daily goal → seed categories suggestion → main menu.
2. **Add manual** → main menu → ➕ Добавить → bot waits text → user sends list → choose category → confirm → main menu.
3. **TXT import** → 📂 Импорт → bot waits file → user sends .txt → preview → choose category → import → main menu.
4. **Study** → 🔥 Учить → mode picker → cards loop → finish summary.
5. **Quick add** → user types `persistent, agile` outside any flow → popup → ✅ → added to default category.
6. **Delete in study** → during card → 🗑 → confirm → next card.
7. **Pack add** → 📦 Паки → category filter (checkboxes) → pack list → preview → "Добавить пак" → main menu.

## 13. What we DO NOT build (per spec)

Mini App, paid AI, public decks, listening mode, shadow learning, voice, scraping, paywalls, admin panel, command-based UX.

## 14. Build order

1. Skeleton + Docker + config + logging.
2. DB models + migrations.
3. Redis + InteractionStateService + middlewares.
4. Word parser + ExampleProvider + repositories.
5. Repetition + StudySession + Progress services.
6. Handlers: onboarding → main menu → add words → txt import → categories → study → packs → progress → settings → fallback/quick-add.
7. Tests + README.
