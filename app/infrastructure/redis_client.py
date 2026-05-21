from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.config import get_settings


def build_redis() -> Redis:
    settings = get_settings()
    return from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
