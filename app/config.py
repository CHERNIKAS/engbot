from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    # "json" for production (structured stdout), "console" for local dev (human-readable).
    log_format: str = Field("json", alias="LOG_FORMAT")

    default_daily_goal: int = Field(10, alias="DEFAULT_DAILY_GOAL")
    txt_max_bytes: int = Field(2_097_152, alias="TXT_MAX_BYTES")  # 2 MB
    txt_max_lines: int = Field(10_000, alias="TXT_MAX_LINES")
    import_max_words: int = Field(5_000, alias="IMPORT_MAX_WORDS")

    interaction_ttl_seconds: int = Field(900, alias="INTERACTION_TTL_SECONDS")
    study_ttl_seconds: int = Field(3_600, alias="STUDY_TTL_SECONDS")

    rate_limit_per_second: int = Field(5, alias="RATE_LIMIT_PER_SECOND")

    # Reminders (daily / streak / inactivity). Sent once per day per user, only
    # within the local-time window below. Anti-spam tracked in Redis.
    # Off by default — push-learning (always on) replaces the once-a-day nudge.
    reminders_enabled: bool = Field(False, alias="REMINDERS_ENABLED")
    reminder_window_start: int = Field(19, alias="REMINDER_WINDOW_START")  # local hour
    reminder_window_end: int = Field(22, alias="REMINDER_WINDOW_END")  # exclusive
    reminder_interval_seconds: int = Field(1800, alias="REMINDER_INTERVAL_SECONDS")

    # Push-learning: bot proactively sends single quiz cards through the day.
    # Opt-in per user; one card in flight at a time; ignored cards are re-pushed
    # at short random intervals until answered, only inside the user's window.
    push_worker_interval_seconds: int = Field(300, alias="PUSH_WORKER_INTERVAL_SECONDS")
    push_default_window_start: int = Field(10, alias="PUSH_DEFAULT_WINDOW_START")
    push_default_window_end: int = Field(22, alias="PUSH_DEFAULT_WINDOW_END")
    push_min_window_hours: int = Field(10, alias="PUSH_MIN_WINDOW_HOURS")
    push_gap_min_minutes: int = Field(10, alias="PUSH_GAP_MIN_MINUTES")  # answered → next card
    push_gap_max_minutes: int = Field(30, alias="PUSH_GAP_MAX_MINUTES")
    push_retry_min_minutes: int = Field(10, alias="PUSH_RETRY_MIN_MINUTES")  # ignored → re-push
    push_retry_max_minutes: int = Field(20, alias="PUSH_RETRY_MAX_MINUTES")
    push_repeat_min_minutes: int = Field(55, alias="PUSH_REPEAT_MIN_MINUTES")  # same-day repeat delay
    push_repeat_max_minutes: int = Field(110, alias="PUSH_REPEAT_MAX_MINUTES")
    push_repeats_per_word: int = Field(2, alias="PUSH_REPEATS_PER_WORD")

    # Pre-shared password required to use the bot. Empty string disables gating.
    access_password: str = Field("", alias="ACCESS_PASSWORD")

    # Feature flag — Japanese track is foundation-only right now (parser is Latin-only,
    # no JA content). Keep it hidden from onboarding & main-menu switcher until the
    # full Japanese flow ships.
    enable_japanese: bool = Field(False, alias="ENABLE_JAPANESE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
