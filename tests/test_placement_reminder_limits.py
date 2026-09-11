"""The reminder promises: at most once a day, at most three times.

The existing fake Redis dropped the expiry argument, so both keys could have
been written with no lifetime at all and every test still passed. And the
three-times limit was only ever compared against its own constant.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.placement_reminder import PlacementReminderService

NOON = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
DAY = 86_400


class _Redis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int | None] = {}

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttl[key] = ex

    async def delete(self, key):
        self.store.pop(key, None)


class _Bot:
    def __init__(self):
        self.sent: list[int] = []
        self._id = 700

    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.sent.append(chat_id)
        self._id += 1
        return SimpleNamespace(message_id=self._id)

    async def delete_message(self, chat_id, message_id):
        pass


class _Session:
    def __init__(self, users):
        self._users = users

    async def execute(self, _stmt):
        users = self._users

        class Result:
            def scalars(self_inner):
                return SimpleNamespace(all=lambda: users)

        return Result()


def _user():
    return SimpleNamespace(id=1, telegram_id=100, level=None, onboarding_completed=True, timezone="UTC")


async def test_the_sent_today_mark_outlives_the_day():
    """With no lifetime (or zero) the mark is gone by the next tick, and the
    same reminder goes out again and again inside one day."""
    redis = _Redis()
    await PlacementReminderService(_Session([_user()]), redis, _Bot()).run(now=NOON)
    day_keys = [k for k in redis.ttl if k.startswith("plreminder:1:")]
    assert day_keys
    for key in day_keys:
        assert redis.ttl[key] is not None and redis.ttl[key] >= DAY, key


async def test_the_reminder_count_is_kept_for_weeks():
    redis = _Redis()
    await PlacementReminderService(_Session([_user()]), redis, _Bot()).run(now=NOON)
    assert redis.ttl["plreminder:count:1"] >= 7 * DAY


async def test_three_reminders_and_then_silence():
    redis, bot = _Redis(), _Bot()
    svc = PlacementReminderService(_Session([_user()]), redis, bot)
    for day in range(5):
        await svc.run(now=NOON + timedelta(days=day))
    assert len(bot.sent) == 3
