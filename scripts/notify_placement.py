"""One-off broadcast: tell users who predate the placement test to take it.

They finished onboarding before the test existed, so `users.level` is NULL and
the gate is holding their bot closed. Without this message they'd just find it
unresponsive and have no idea why.

Idempotent by construction — it only writes Telegram messages, and it selects on
`level IS NULL`, so a user who has already taken the test is skipped on a rerun.

Run inside the bot container:
    docker exec -w /app englshbot-bot-1 python scripts/notify_placement.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.keyboards.onboarding import placement_gate_kb
from app.bot.texts import PLACEMENT_GATE
from app.config import get_settings
from app.domain.levels import TEST_LEVELS, TEST_PER_LEVEL
from app.domain.models import User


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="list recipients, send nothing")
    args = ap.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(User.telegram_id).where(
                    User.level.is_(None),
                    User.onboarding_completed.is_(True),
                )
            )
        ).scalars().all()

    print(f"recipients: {len(rows)}")
    if args.dry_run:
        for tid in rows:
            print(f"  would notify {tid}")
        await engine.dispose()
        return

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    text = PLACEMENT_GATE.format(total=len(TEST_LEVELS) * TEST_PER_LEVEL)
    sent = failed = 0
    try:
        for tid in rows:
            try:
                await bot.send_message(tid, text, reply_markup=placement_gate_kb())
                sent += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 1)
                await bot.send_message(tid, text, reply_markup=placement_gate_kb())
                sent += 1
            except TelegramForbiddenError:
                # Blocked the bot. Nothing to do and nothing to fix — the gate
                # will show the same screen if they ever come back.
                failed += 1
            # Telegram's broadcast ceiling is ~30 messages/second; this is a
            # handful of users, so one message every other tick is plenty.
            await asyncio.sleep(0.5)
    finally:
        await bot.session.close()
        await engine.dispose()

    print(f"sent: {sent}, unreachable: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
