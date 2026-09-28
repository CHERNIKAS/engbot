from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError

from app.bot.errors import register_error_handler
from app.bot.handlers import register_handlers
from app.bot.middlewares.auth_gate import AuthGateMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.interaction_guard import InteractionGuardMiddleware
from app.bot.middlewares.logging_context import LoggingContextMiddleware
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.bot.middlewares.services import ServicesMiddleware
from app.bot.middlewares.user_loader import UserLoaderMiddleware
from app.bot.texts import REGRADE_NOTHING, REGRADE_NOTICE
from app.config import get_settings
from app.infrastructure.db.engine import build_engine, build_sessionmaker
from app.infrastructure.example_provider.local_json import LocalJsonExampleProvider
from app.infrastructure.redis_client import build_redis
from app.logging_setup import get_logger, setup_logging
from app.services.digest_service import DigestService
from app.services.level_tagger import LevelTaggerService
from app.services.regrade import RegradeService
from app.services.interaction_state_service import InteractionStateService
from app.services.push_service import PushService
from app.services.reminder_service import ReminderService
from app.services.screen_service import ScreenVersionService
from app.services.track_context_service import TrackContextService


async def _reminder_worker(sessionmaker, redis, bot) -> None:
    settings = get_settings()
    log = get_logger("reminders")
    while True:
        await asyncio.sleep(settings.reminder_interval_seconds)
        try:
            async with sessionmaker() as session:
                sent = await ReminderService(session, redis, bot).run()
                await session.commit()
            if sent:
                log.info("reminders_sent", count=sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("reminder_worker_error")


async def _push_worker(sessionmaker, redis, bot) -> None:
    settings = get_settings()
    log = get_logger("push")
    while True:
        await asyncio.sleep(settings.push_worker_interval_seconds)
        try:
            async with sessionmaker() as session:
                await PushService(session, redis, bot).run_all()
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("push_worker_error")


async def _digest_worker(sessionmaker, redis, bot) -> None:
    settings = get_settings()
    log = get_logger("digest")
    while True:
        await asyncio.sleep(settings.digest_interval_seconds)
        try:
            async with sessionmaker() as session:
                sent = await DigestService(session, redis, bot).run()
                await session.commit()
            if sent:
                log.info("digests_sent", count=sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("digest_worker_error")



async def _level_tagger_worker(sessionmaker) -> None:
    """Fills level/freq_rank on words users added since the last backfill.
    Off unless GEMINI_API_KEY is set; an untagged word still works everywhere,
    it just can't be matched to a user's level until this catches up."""
    settings = get_settings()
    log = get_logger("level_tagger")
    while True:
        await asyncio.sleep(settings.level_tagger_interval_seconds)
        try:
            async with sessionmaker() as session:
                await LevelTaggerService(session).run()
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("level_tagger_worker_error")



async def _regrade_worker(sessionmaker, redis, bot) -> None:
    """Re-scores answers that were marked strictly while the checker was down,
    and tells the user what changed. Off without a key — with no checker there
    is nothing to have been degraded from."""
    settings = get_settings()
    log = get_logger("regrade")
    while True:
        await asyncio.sleep(settings.regrade_interval_seconds)
        try:
            async with sessionmaker() as session:
                result = await RegradeService(session, redis).run(
                    now=datetime.now(timezone.utc).timestamp()
                )
                await session.commit()
            for telegram_id in result.rechecked or set():
                lines = (result.per_user or {}).get(telegram_id)
                # Upgraded → say what changed. Rechecked and unchanged → still
                # say so: the card promised a recount, and a kept promise the
                # user never hears about is indistinguishable from a dropped one.
                text = (
                    REGRADE_NOTICE.format(lines="\n".join(f"• {ln}" for ln in lines[:10]))
                    if lines
                    else REGRADE_NOTHING
                )
                try:
                    await bot.send_message(telegram_id, text)
                except TelegramForbiddenError:
                    pass  # blocked the bot; the score was applied regardless
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("regrade_worker_error")



async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    log = get_logger("main")

    engine = build_engine()
    sessionmaker = build_sessionmaker(engine)
    redis = build_redis()

    state_service = InteractionStateService(redis)
    screen_service = ScreenVersionService(redis)
    track_context = TrackContextService(redis)
    example_provider = LocalJsonExampleProvider()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()

    # Workflow data — handlers pull these by kwarg name.
    dp["state_service"] = state_service
    dp["screen_service"] = screen_service
    dp["track_context"] = track_context
    dp["example_provider"] = example_provider
    dp["redis"] = redis

    logging_ctx = LoggingContextMiddleware()
    rate_limit = RateLimitMiddleware(redis, per_second=settings.rate_limit_per_second)
    db_mw = DbSessionMiddleware(sessionmaker)
    user_mw = UserLoaderMiddleware()
    services_mw = ServicesMiddleware(redis, track_context)
    auth_gate = AuthGateMiddleware(
        access_password=settings.access_password,
        state_service=state_service,
    )
    guard_mw = InteractionGuardMiddleware(state_service)

    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware.register(logging_ctx)
        observer.outer_middleware.register(rate_limit)
        observer.outer_middleware.register(db_mw)
        observer.outer_middleware.register(user_mw)
        observer.outer_middleware.register(services_mw)
        observer.outer_middleware.register(auth_gate)
        # The placement gate used to sit here, holding the whole bot closed
        # until the user had a level. The level is now derived from mastered
        # words when the day's plan is built, so there is nothing to wait for.
        observer.outer_middleware.register(guard_mw)

    register_handlers(dp)
    register_error_handler(dp)

    background: list[asyncio.Task] = []
    if settings.reminders_enabled:
        background.append(asyncio.create_task(_reminder_worker(sessionmaker, redis, bot)))
    background.append(asyncio.create_task(_push_worker(sessionmaker, redis, bot)))
    if settings.digest_enabled:
        background.append(asyncio.create_task(_digest_worker(sessionmaker, redis, bot)))
    if settings.gemini_api_key:
        background.append(asyncio.create_task(_level_tagger_worker(sessionmaker)))
        background.append(asyncio.create_task(_regrade_worker(sessionmaker, redis, bot)))

    log.info("bot_starting")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Cancel workers and WAIT for them to unwind before tearing down the
        # resources they use — otherwise a cancelled worker's `async with
        # sessionmaker()` __aexit__ runs against an already-disposed engine.
        for task in background:
            task.cancel()
        await asyncio.gather(*background, return_exceptions=True)
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
