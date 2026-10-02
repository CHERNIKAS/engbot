"""One-off broadcast to every onboarded learner.

A separate script, run by hand, never from the push worker. Three properties
matter and each exists because of something that already went wrong here:

* **It never touches `push:*`.** Not a read, not a write. The July spam bug was
  one writer clobbering that state with a stale snapshot, and a broadcast that
  opened it would join the same class of problem. Nothing here imports the push
  service at all.

* **It does not stop the bot.** Stopping was considered and rejected: `inflight`
  lives in Redis with a TTL, so a stop does not clear it — but while the bot is
  down every tap on a card lands nowhere and Telegram shows «истекло». We would
  break cards for whoever is mid-answer in order to announce an improvement.

* **It will not send twice.** Each delivery is recorded in
  `user_tracks.settings.broadcasts`, and a second run skips anyone already
  there. A broadcast repeated because somebody re-ran the command is worse than
  one never sent.

Sending requires `--send`. Without it the script prints the audience and the
text and exits, which is the mode meant for review.

    python scripts/broadcast.py --slug v2 --text-file /tmp/v2.txt
    python scripts/broadcast.py --slug v2 --text-file /tmp/v2.txt --send
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.bot.keyboards.main_menu import main_menu_reply_kb  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.domain.models import User, UserTrack  # noqa: E402

SETTINGS_KEY = "broadcasts"


async def audience(session) -> list[tuple[User, UserTrack | None]]:
    """Onboarded learners, with their English track row if they have one.

    Users who blocked the bot are included in the listing but marked: Telegram
    will refuse the send, and seeing them in the report is more useful than
    silently having a smaller audience than expected.
    """
    rows = (
        await session.execute(
            select(User, UserTrack)
            .outerjoin(
                UserTrack,
                (UserTrack.user_id == User.id) & (UserTrack.track == "en"),
            )
            .where(User.onboarding_completed.is_(True))
            .order_by(User.id)
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


def already_sent(track: UserTrack | None, slug: str) -> bool:
    if track is None:
        return False
    return slug in ((track.settings or {}).get(SETTINGS_KEY) or [])


def blocked(track: UserTrack | None) -> bool:
    return bool(track and (track.settings or {}).get("push_blocked"))


def mark_sent(track: UserTrack, slug: str) -> None:
    settings = dict(track.settings or {})
    sent = list(settings.get(SETTINGS_KEY) or [])
    if slug not in sent:
        sent.append(slug)
    settings[SETTINGS_KEY] = sent
    # Reassign: SQLAlchemy does not track mutations inside a JSONB column, so
    # editing in place would flush nothing and the next run would send again.
    track.settings = settings


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="broadcast id, recorded per user")
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--send", action="store_true", help="actually send; off by default")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between messages")
    ap.add_argument(
        "--with-menu",
        action="store_true",
        help="attach the bottom menu — the only way to replace a stale one",
    )
    args = ap.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        sys.exit("текст пустой")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        people = await audience(session)
        pending = [
            (u, t) for u, t in people if not already_sent(t, args.slug) and not blocked(t)
        ]
        skipped_sent = [u.id for u, t in people if already_sent(t, args.slug)]
        skipped_blocked = [u.id for u, t in people if blocked(t) and not already_sent(t, args.slug)]

        print(f"всего онбордившихся: {len(people)}")
        print(f"получат сейчас:      {len(pending)} → {[u.id for u, _ in pending]}")
        print(f"уже получали:        {len(skipped_sent)} → {skipped_sent}")
        print(f"заблокировали бота:  {len(skipped_blocked)} → {skipped_blocked}")
        print(f"пауза между:         {args.delay} c")
        print("-" * 60)
        print(text)
        print("-" * 60)

        if not args.send:
            print("ЧЕРНОВИК: ничего не отправлено. Для отправки добавь --send")
            await engine.dispose()
            return

        # A ReplyKeyboardMarkup lives on the client until a message carries a
        # new one. After the menu was rebuilt, everyone who never typed /start
        # kept the old buttons, and there is no API to press it for them — so
        # a message that carries the keyboard is the only way to replace it.
        kb = main_menu_reply_kb() if args.with_menu else None

        bot = Bot(token=settings.bot_token)
        ok = failed = 0
        try:
            for user, track in pending:
                try:
                    await bot.send_message(user.telegram_id, text, parse_mode="HTML", reply_markup=kb)
                except TelegramRetryAfter as exc:
                    # Telegram throttles bulk sends; obeying it is the whole
                    # reason for the pause between messages.
                    print(f"uid={user.id} throttled, ждём {exc.retry_after}s")
                    await asyncio.sleep(exc.retry_after + 1)
                    try:
                        await bot.send_message(user.telegram_id, text, parse_mode="HTML", reply_markup=kb)
                    except Exception as exc2:  # noqa: BLE001
                        failed += 1
                        print(f"uid={user.id} ОШИБКА после retry: {exc2!r}")
                        continue
                except TelegramForbiddenError:
                    failed += 1
                    print(f"uid={user.id} ОШИБКА: бот заблокирован")
                    continue
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"uid={user.id} ОШИБКА: {exc!r}")
                    continue

                ok += 1
                print(f"uid={user.id} отправлено")
                if track is not None:
                    mark_sent(track, args.slug)
                    await session.commit()
                await asyncio.sleep(args.delay)
        finally:
            await bot.session.close()
            await engine.dispose()

        print("-" * 60)
        print(f"отправлено {ok}, ошибок {failed}")
        if failed:
            print("повторный запуск отправит только тем, у кого отметки нет")


if __name__ == "__main__":
    asyncio.run(main())
