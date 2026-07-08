from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    # "json" for production (structured stdout), "console" for local dev (human-readable).
    log_format: str = Field("json", alias="LOG_FORMAT")

    default_daily_goal: int = Field(10, ge=1, le=500, alias="DEFAULT_DAILY_GOAL")
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
    reminder_window_start: int = Field(19, ge=0, le=23, alias="REMINDER_WINDOW_START")  # local hour
    reminder_window_end: int = Field(22, ge=1, le=24, alias="REMINDER_WINDOW_END")  # exclusive
    reminder_interval_seconds: int = Field(1800, ge=30, alias="REMINDER_INTERVAL_SECONDS")

    # Push-learning: bot proactively sends single quiz cards through the day.
    # Opt-in per user; one card in flight at a time; ignored cards are re-pushed
    # at short random intervals until answered, only inside the user's window.
    push_worker_interval_seconds: int = Field(300, ge=10, alias="PUSH_WORKER_INTERVAL_SECONDS")
    push_default_window_start: int = Field(10, ge=0, le=23, alias="PUSH_DEFAULT_WINDOW_START")
    push_default_window_end: int = Field(22, ge=1, le=24, alias="PUSH_DEFAULT_WINDOW_END")
    push_min_window_hours: int = Field(10, ge=1, le=24, alias="PUSH_MIN_WINDOW_HOURS")
    push_gap_min_minutes: int = Field(2, ge=1, alias="PUSH_GAP_MIN_MINUTES")  # answered → next card (random)
    push_gap_max_minutes: int = Field(15, ge=1, alias="PUSH_GAP_MAX_MINUTES")

    # Weekly digest — the bot's once-a-week recap (answers, accuracy, mastered
    # delta, toughest word). Sent inside the local-time window on digest_weekday
    # (Python convention: 0 = Monday … 6 = Sunday). Dedup per ISO week in Redis.
    digest_enabled: bool = Field(True, alias="DIGEST_ENABLED")
    digest_weekday: int = Field(6, ge=0, le=6, alias="DIGEST_WEEKDAY")  # 0=Mon..6=Sun
    digest_window_start: int = Field(19, ge=0, le=23, alias="DIGEST_WINDOW_START")  # local hour
    digest_window_end: int = Field(22, ge=1, le=24, alias="DIGEST_WINDOW_END")  # exclusive
    digest_interval_seconds: int = Field(1800, ge=30, alias="DIGEST_INTERVAL_SECONDS")

    # Pre-shared password required to use the bot. Empty string disables gating.
    access_password: str = Field("", alias="ACCESS_PASSWORD")

    # Feature flag — Japanese track is foundation-only right now (parser is Latin-only,
    # no JA content). Keep it hidden from onboarding & main-menu switcher until the
    # full Japanese flow ships.
    enable_japanese: bool = Field(False, alias="ENABLE_JAPANESE")

    @model_validator(mode="after")
    def _check_windows(self) -> "Settings":
        # A window's end must be after its start (24 = midnight). Catches an
        # inverted daytime window at startup rather than letting it silently
        # never open. (Overnight PUSH windows are per-user and normalized
        # elsewhere; these are the daytime reminder/digest defaults.)
        for name, s, e in (
            ("reminder", self.reminder_window_start, self.reminder_window_end),
            ("digest", self.digest_window_start, self.digest_window_end),
        ):
            if e <= s:
                raise ValueError(f"{name} window end ({e}) must be after start ({s})")
        for lo, hi, a, b in (("gap", "min/max", self.push_gap_min_minutes, self.push_gap_max_minutes),):
            if b < a:
                raise ValueError(f"push {lo} {hi}: max ({b}) < min ({a})")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
