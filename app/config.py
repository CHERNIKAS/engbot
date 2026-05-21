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

    # Pre-shared password required to use the bot. Empty string disables gating.
    access_password: str = Field("", alias="ACCESS_PASSWORD")

    # Feature flag — Japanese track is foundation-only right now (parser is Latin-only,
    # no JA content). Keep it hidden from onboarding & main-menu switcher until the
    # full Japanese flow ships.
    enable_japanese: bool = Field(False, alias="ENABLE_JAPANESE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
