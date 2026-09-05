from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aiogram.exceptions import TelegramForbiddenError

from app.services.placement_reminder import _MAX_REMINDERS, PlacementReminderService

# Inside the default push window (10:00–22:00) in UTC.
NOON = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


def forbidden() -> TelegramForbiddenError:
    """aiogram's exception needs a method and a message; a bare class raises
    TypeError instead and would be caught by the wrong branch."""
    return TelegramForbiddenError(method=None, message="bot was blocked by the user")


class FakeBot:
    def __init__(self, fail: Exception | None = None):
        self.sent: list[int] = []
        self._fail = fail

    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        if self._fail is not None:
            raise self._fail
        self.sent.append(chat_id)


def _user(uid=1, tg=100, level=None, onboarded=True, tz="UTC"):
    return SimpleNamespace(
        id=uid, telegram_id=tg, level=level, onboarding_completed=onboarded, timezone=tz
    )


class FakeSession:
    def __init__(self, users):
        self._users = users

    async def execute(self, _stmt):
        users = self._users

        class Result:
            def scalars(self_inner):
                return SimpleNamespace(all=lambda: users)

        return Result()


def _service(users, redis=None, bot=None):
    return PlacementReminderService(FakeSession(users), redis or FakeRedis(), bot or FakeBot())


async def test_a_blocked_user_is_reminded():
    bot = FakeBot()
    svc = _service([_user()], bot=bot)
    assert await svc.run(now=NOON) == 1
    assert bot.sent == [100]


async def test_only_once_per_day():
    bot, redis = FakeBot(), FakeRedis()
    svc = _service([_user()], redis=redis, bot=bot)
    await svc.run(now=NOON)
    await svc.run(now=NOON + timedelta(hours=3))
    assert bot.sent == [100]


async def test_the_next_day_reminds_again():
    bot, redis = FakeBot(), FakeRedis()
    svc = _service([_user()], redis=redis, bot=bot)
    await svc.run(now=NOON)
    await svc.run(now=NOON + timedelta(days=1))
    assert len(bot.sent) == 2


async def test_nothing_arrives_outside_the_window():
    """A nudge at 4am is how a bot gets blocked rather than opened."""
    bot = FakeBot()
    await _service([_user()], bot=bot).run(now=NIGHT)
    assert bot.sent == []


async def test_the_window_follows_the_user_timezone():
    bot = FakeBot()
    # 04:00 UTC is 14:00 in Vladivostok — inside their day, not ours.
    await _service([_user(tz="Asia/Vladivostok")], bot=bot).run(now=NIGHT)
    assert bot.sent == [100]


async def test_it_gives_up_after_a_handful_of_tries():
    """Every reminder is the same text, so one that keeps arriving after
    someone has read it twice and done nothing stops being a reminder."""
    bot, redis = FakeBot(), FakeRedis()
    svc = _service([_user()], redis=redis, bot=bot)
    for day in range(_MAX_REMINDERS + 3):
        await svc.run(now=NOON + timedelta(days=day))
    assert len(bot.sent) == _MAX_REMINDERS


async def test_blocking_the_bot_stops_the_reminders_immediately():
    """No point retrying daily into a closed door."""
    bot, redis = FakeBot(fail=forbidden()), FakeRedis()
    svc = _service([_user()], redis=redis, bot=bot)
    await svc.run(now=NOON)
    good = FakeBot()
    svc2 = _service([_user()], redis=redis, bot=good)
    await svc2.run(now=NOON + timedelta(days=1))
    assert good.sent == []


async def test_one_failed_send_does_not_stop_the_others():
    class Flaky(FakeBot):
        async def send_message(self, chat_id, text, reply_markup=None, **kw):
            if chat_id == 100:
                raise RuntimeError("telegram hiccup")
            self.sent.append(chat_id)

    bot = Flaky()
    await _service([_user(1, 100), _user(2, 200)], bot=bot).run(now=NOON)
    assert bot.sent == [200]
