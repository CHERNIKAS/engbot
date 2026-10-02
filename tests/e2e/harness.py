"""A fake Telegram around the real bot.

Everything from the dispatcher down is production code: routers, middlewares,
handlers, PushService, Postgres, Redis. Only the Telegram API is replaced — by a
session that records what was sent, edited, deleted and toasted, and hands out
message ids — so a test can tap the buttons the bot actually sent and read what
the learner would see.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy import text

from app.bot.texts import GENERIC_ERROR, PUSH_STALE

TG_ID = 481638710  # learner 1 in the restored copy
UID = 1
_ids = itertools.count(5_000_000)
# Every push action tapped in this session; the coverage test reads it.
TAPPED: set[str] = set()
# Every handler that ran in this session, as "module.function".
HANDLERS_RUN: set[str] = set()


def handler_name(fn) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


class _HandlerSeen:
    """Inner middleware: notes which handler an update reached."""

    async def __call__(self, handler, event, data):
        obj = data.get("handler")
        if obj is not None:
            HANDLERS_RUN.add(handler_name(obj.callback))
        return await handler(event, data)


_seen_installed = False


def install_handler_tracking(dp) -> None:
    """Once per process: routers are module-level, and so are their middlewares."""
    global _seen_installed
    if _seen_installed:
        return
    seen = _HandlerSeen()
    for router in dp.sub_routers:
        router.message.middleware(seen)
        router.callback_query.middleware(seen)
    _seen_installed = True


def all_handlers(dp) -> set[str]:
    return {
        handler_name(h.callback)
        for router in dp.sub_routers
        for obs in (router.message, router.callback_query)
        for h in obs.handlers
    }


def action_of(data: str) -> str:
    parts = data.split(":")
    return parts[1] if len(parts) > 1 and parts[0] == "pu" else parts[0]


class FakeTelegram(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.next_msg = itertools.count(900_000)
        self.live: dict[int, dict] = {}  # message_id → {"text", "markup"}
        self.sent: list[dict] = []
        self.deleted: list[int] = []
        self.edits: list[int] = []
        self.toasts: list[str | None] = []
        self.files: dict[str, bytes] = {}  # file_path → content, for downloads

    async def close(self) -> None:
        pass

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield self.files.get(url.rsplit("/", 1)[-1], b"")

    def dummy(self) -> int:
        """A message to tap a hand-built button from."""
        mid = next(self.next_msg)
        self.live[mid] = {"id": mid, "text": "·", "markup": None, "reply_kb": None}
        return mid

    async def make_request(self, bot: Bot, method, timeout=None):
        name = type(method).__name__
        if name == "SendMessage":
            mid = next(self.next_msg)
            markup = method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None
            entry = {"id": mid, "text": method.text, "markup": markup, "reply_kb": method.reply_markup}
            self.live[mid] = entry
            self.sent.append(entry)
            return Message.model_validate(
                {
                    "message_id": mid,
                    "date": int(datetime.now(timezone.utc).timestamp()),
                    "chat": {"id": method.chat_id, "type": "private"},
                    "text": method.text,
                },
                context={"bot": bot},
            )
        if name == "EditMessageText":
            self.edits.append(method.message_id)
            if method.message_id in self.live:
                self.live[method.message_id]["text"] = method.text
                self.live[method.message_id]["markup"] = method.reply_markup
            return True
        if name == "EditMessageReplyMarkup":
            if method.message_id in self.live:
                self.live[method.message_id]["markup"] = method.reply_markup
            return True
        if name == "DeleteMessage":
            self.deleted.append(method.message_id)
            self.live.pop(method.message_id, None)
            return True
        if name == "AnswerCallbackQuery":
            self.toasts.append(method.text)
            return True
        if name == "GetFile":
            from aiogram.types import File

            return File(file_id=method.file_id, file_unique_id=method.file_id, file_path=f"{method.file_id}.txt")
        return True

    # ---- reading the chat ----

    def buttons(self, mid: int) -> list[tuple[str, str]]:
        markup = self.live[mid]["markup"]
        if markup is None:
            return []
        return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row if b.callback_data]

    def last_with_buttons(self) -> dict:
        for entry in reversed(self.sent):
            if entry["id"] in self.live and self.live[entry["id"]]["markup"] is not None:
                return self.live[entry["id"]]
        raise AssertionError("no live message with buttons")

    def errors(self) -> list[str]:
        out = [t for t in self.toasts if t and GENERIC_ERROR in t]
        out += [e["text"] for e in self.sent if e["text"] and GENERIC_ERROR in e["text"]]
        return out


class Harness:
    def __init__(self, dp, bot: Bot, tg: FakeTelegram, sessionmaker, redis) -> None:
        self.dp, self.bot, self.tg, self.sm, self.redis = dp, bot, tg, sessionmaker, redis

    # ---- driving the bot like a learner ----

    tg_id = TG_ID

    def _from(self) -> dict:
        return {"id": self.tg_id, "is_bot": False, "first_name": "E2E"}

    def _view(self):
        return (
            {k: (v["text"], repr(v["markup"])) for k, v in self.tg.live.items()},
            len(self.tg.sent),
            len([t for t in self.tg.toasts if t]),
        )

    async def tap(self, mid: int, data: str, silent_ok: bool = False) -> None:
        """Tap a button. Fails if the learner would see nothing happen — no
        edit that changes the card, no new message, no toast with text: that is
        the «button doesn't answer» report, whatever the cause."""
        before = self._view()
        await self._tap(mid, data)
        if not silent_ok:
            assert self._view() != before, f"tap {data!r} on {mid} gave no visible response"

    def data_by_action(self, mid: int, action: str, nth: int = 0) -> str:
        found = [d for _t, d in self.tg.buttons(mid) if action_of(d) == action]
        assert len(found) > nth, f"no {action!r} button on {mid}: {self.tg.buttons(mid)}"
        return found[nth]

    async def act(self, mid: int, action: str, nth: int = 0, silent_ok: bool = False) -> None:
        await self.tap(mid, self.data_by_action(mid, action, nth), silent_ok=silent_ok)

    async def _tap(self, mid: int, data: str) -> None:
        TAPPED.add(action_of(data))
        msg = self.tg.live.get(mid, {"text": "gone"})
        update = {
            "update_id": next(_ids),
            "callback_query": {
                "id": str(next(_ids)),
                "from": self._from(),
                "chat_instance": "e2e",
                "data": data,
                "message": {
                    "message_id": mid,
                    "date": int(datetime.now(timezone.utc).timestamp()),
                    "chat": {"id": self.tg_id, "type": "private"},
                    "text": msg.get("text") or "",
                },
            },
        }
        await self.dp.feed_raw_update(self.bot, update)

    def data_for(self, mid: int, label: str) -> str:
        for text_, data in self.tg.buttons(mid):
            if text_ == label or text_.strip() == label.strip():
                return data
        raise AssertionError(f"no button {label!r} on {mid}: {[t for t, _ in self.tg.buttons(mid)]}")

    async def tap_text(self, mid: int, label: str, silent_ok: bool = False) -> None:
        for text_, data in self.tg.buttons(mid):
            if text_ == label or text_.strip() == label.strip():
                return await self.tap(mid, data, silent_ok=silent_ok)
        raise AssertionError(f"no button {label!r} on {mid}: {[t for t, _ in self.tg.buttons(mid)]}")

    async def say(self, words: str, silent_ok: bool = False) -> None:
        before = self._view()
        await self._say(words)
        if not silent_ok:
            assert self._view() != before, f"message {words!r} gave no visible response"

    async def _say(self, words: str) -> None:
        await self._send_message({"text": words})

    async def _send_message(self, body: dict) -> None:
        update = {
            "update_id": next(_ids),
            "message": {
                "message_id": next(_ids),
                "date": int(datetime.now(timezone.utc).timestamp()),
                "chat": {"id": self.tg_id, "type": "private"},
                "from": self._from(),
                **body,
            },
        }
        await self.dp.feed_raw_update(self.bot, update)

    async def send_document(self, name: str, content: bytes) -> None:
        file_id = f"doc{next(_ids)}"
        self.tg.files[f"{file_id}.txt"] = content
        await self._send_message({"document": {
            "file_id": file_id, "file_unique_id": file_id, "file_name": name,
            "mime_type": "text/plain", "file_size": len(content),
        }})

    async def send_sticker(self) -> None:
        await self._send_message({"sticker": {
            "file_id": "st", "file_unique_id": "st", "type": "regular",
            "width": 512, "height": 512, "is_animated": False, "is_video": False,
        }})

    async def tick(self) -> bool:
        """One worker tick for the learner, as `run_all` does it."""
        from app.infrastructure.repositories.user_tracks import UserTrackRepository
        from app.infrastructure.repositories.users import UserRepository
        from app.services import push_service as ps

        async with self.sm() as session:
            svc = ps.PushService(session, self.redis, self.bot)
            user = await UserRepository(session).get(UID)
            ut = await UserTrackRepository(session).get(UID, ps._TRACK)
            async with ps._user_lock(UID):
                sent = await svc.run_tick(user, ut)
            await session.commit()
            return sent

    async def run_lessons(self) -> None:
        from app.services.push_service import PushService

        async with self.sm() as session:
            await PushService(session, self.redis, self.bot).run_lessons()
            await session.commit()

    # ---- reading state ----

    async def state(self) -> dict:
        raw = await self.redis.get(f"push:{UID}")
        return json.loads(raw) if raw else {}

    async def put_state(self, state: dict) -> None:
        await self.redis.set(f"push:{UID}", json.dumps(state, ensure_ascii=False))

    async def patch_inflight(self, **fields) -> None:
        st = await self.state()
        st["inflight"].update(fields)
        await self.put_state(st)

    async def sql(self, q: str, **params) -> list:
        async with self.sm() as session:
            res = await session.execute(text(q), params)
            await session.commit()
            try:
                return list(res.all())
            except Exception:  # noqa: BLE001 — statements without rows
                return []

    async def plan(self) -> list[dict]:
        rows = await self.sql(
            "select items from day_plans where user_id=:u and closed_at is null", u=UID
        )
        return rows[0][0] if rows else []

    async def done_kinds(self) -> list[str]:
        return [i["kind"] for i in await self.plan() if i.get("done")]

    # ---- arranging a day ----

    async def fresh_day(self, kinds: list[str]) -> None:
        """A clean slate: no cards in flight, a plan of exactly `kinds`, the
        push window open all day, every grammar rule already introduced."""
        await self.redis.flushdb()
        await self.sql("delete from day_plans where user_id=:u", u=UID)
        await self.sql(
            "update user_tracks set settings = coalesce(settings,'{}'::jsonb)"
            " || '{\"push_ws\": 0, \"push_we\": 24}'::jsonb where user_id=:u",
            u=UID,
        )
        await self.sql(
            "update user_grammar_topics set rule_seen_at = coalesce(rule_seen_at, now()) where user_id=:u",
            u=UID,
        )
        today = await self.today()
        items = json.dumps([{"kind": k, "done": False} for k in kinds])
        await self.sql(
            "insert into day_plans (user_id, track, size, items, opened_on) values (:u, 'en', :n, cast(:i as jsonb), :d)",
            u=UID, n=len(kinds), i=items, d=today,
        )
        await self.put_state({"day": today.isoformat(), "next_ts": 0.0, "inflight": None, "new_today": 0})

    async def today(self):
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Moscow")).date()

    async def card(self) -> dict:
        """Tick until a card is in flight (a rule card may come first)."""
        for _ in range(4):
            st = await self.state()
            if st.get("inflight"):
                return st["inflight"]
            st["next_ts"] = 0.0
            await self.put_state(st)
            await self.tick()
        st = await self.state()
        assert st.get("inflight"), f"no card in flight; sent={[e['text'][:40] for e in self.tg.sent]}"
        return st["inflight"]

    async def check_invariants(self) -> None:
        """What must hold after any sequence of taps and ticks."""
        assert self.tg.errors() == [], f"handler crashed: {self.tg.errors()}"
        st = await self.state()
        inflight = st.get("inflight")
        if inflight:
            assert inflight.get("msg_id") in self.tg.live, "the card in flight is not in the chat"
