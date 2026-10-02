"""End-to-end card flows against a throwaway Postgres + Redis.

Skipped unless E2E_DATABASE_URL and E2E_REDIS_URL are set. E2E_DATABASE_URL names
a *template*: a disposable restored copy that is never written to. Every test
gets its own database cloned from it (CREATE DATABASE … TEMPLATE), so scenarios
cannot use up each other's words. Never point these at production.
See tests/e2e/README.md.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
import pytest_asyncio

DB = os.environ.get("E2E_DATABASE_URL")
REDIS = os.environ.get("E2E_REDIS_URL")

pytestmark = pytest.mark.skipif(not (DB and REDIS), reason="E2E_DATABASE_URL / E2E_REDIS_URL not set")


def pytest_collection_modifyitems(config, items):
    if DB and REDIS:
        return
    skip = pytest.mark.skip(reason="E2E_DATABASE_URL / E2E_REDIS_URL not set")
    for item in items:
        if "/e2e/" in str(item.fspath):
            item.add_marker(skip)


async def _fresh_clone(template_url: str) -> str:
    """Drop and re-create `<template>_run` from the template; return its URL."""
    import asyncpg
    from sqlalchemy.engine import make_url

    u = make_url(template_url)
    run_db = f"{u.database}_run"
    admin = await asyncpg.connect(
        host=u.host, port=u.port, user=u.username, password=u.password, database="postgres"
    )
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{run_db}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{run_db}" TEMPLATE "{u.database}"')
    finally:
        await admin.close()
    return u.set(database=run_db).render_as_string(hide_password=False)


@pytest_asyncio.fixture
async def h(monkeypatch):
    from aiogram import Bot
    from redis.asyncio import from_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.main import build_dispatcher
    from app.services import push_service as ps

    # One event loop per test here, one for the life of the process in prod:
    # a lock left from the previous test is bound to a loop that is gone.
    ps._USER_LOCKS.clear()
    # The scenarios need the push window open whatever the clock says; a
    # 24-hour window is not a valid setting (normalize_window falls back to
    # 10–22), so the window itself is pinned.
    monkeypatch.setattr(ps.PushService, "_window", lambda self, user, ut: (0, 24))
    from tests.e2e.harness import FakeTelegram, Harness, install_handler_tracking

    assert "55481" in DB or os.environ.get("E2E_I_KNOW"), "refusing: E2E_DATABASE_URL does not look disposable"
    url = await _fresh_clone(DB)
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    redis = from_url(REDIS, decode_responses=True)
    tg = FakeTelegram()
    bot = Bot(token="123456:E2E", session=tg)
    dp = build_dispatcher(SimpleNamespace(rate_limit_per_second=1000, access_password=""), redis, sm)
    install_handler_tracking(dp)
    harness = Harness(dp, bot, tg, sm, redis)

    async def reset() -> None:
        """A fresh clone and an empty Redis, mid-test: the crawler isolates
        each entry point so one path's side effects do not hide another's."""
        await engine.dispose()
        await _fresh_clone(DB)
        await redis.flushdb()

    harness.reset = reset
    try:
        yield harness
    finally:
        # Routers are module-level and refuse a second parent; release them so
        # the next test can build its own dispatcher.
        for router in list(dp.sub_routers):
            router._parent_router = None
        await redis.aclose()
        await engine.dispose()
