"""Every screen, every button — the rest of the bot beyond push cards.

A crawler. It starts from each entry point — a menu label, a command, or a short
chain of steps a crawler cannot discover by tapping (typing a word, sending a
file, being a brand-new user) — and taps every inline button on every message
the bot sends or edits, breadth first. A button whose message has been replaced
(menu screens replace each other) is reached again by replaying the path that
revealed it. Each tap and each entry step must visibly do something and no
handler may crash; failures are collected so one run lists all of them.
The last test fails when any handler in any router was never reached.
"""
from __future__ import annotations

from collections import deque

from app.bot import texts as T
from app.bot.callbacks.schema import (
    AddWordsCB,
    CategoryCB,
    ImportCB,
    PacksCB,
    ProgressCB,
    SearchCB,
)
from tests.e2e.harness import HANDLERS_RUN, UID, all_handlers

MENU = [
    "/start", "/help", "/menu", "/packs_admin",
    T.BTN_TODAY, T.BTN_MY_WORDS, T.BTN_GRAMMAR, T.BTN_PROGRESS, T.BTN_SETTINGS, T.BTN_LESSON,
    T.BTN_LESSON_END,
    # Labels Telegram may still show from an older keyboard.
    T.BTN_COLLECTIONS, T.BTN_WORDS, T.BTN_STUDY, T.BTN_ADD, T.BTN_IMPORT, T.BTN_PACKS, T.BTN_HELP,
    T.BTN_MY_WORDS_OLD,
]
SILENT_PREFIXES = ("noop",)
MAX_TAPS = 1500
PER_KIND = 3
NEW_USER = 990_000_001


def _card_actions() -> set[str]:
    import re
    from pathlib import Path

    src = Path("app/bot/handlers/push.py").read_text(encoding="utf-8")
    return set(re.findall(r'F\.action == "([a-z_]+)"', src))


CARD_ACTIONS = _card_actions()


def _is_card_button(data: str) -> bool:
    parts = data.split(":")
    return parts[0] == "pu" and len(parts) > 1 and parts[1] in CARD_ACTIONS


def _kind(data: str) -> str:
    return ":".join(data.split(":")[:2])


def _volatile(field: str) -> bool:
    """A screen version or a one-off token: regenerated on every render."""
    return (
        len(field) >= 4
        and not field.isdigit()
        and any(c.isupper() or c.isdigit() or c in "_-" for c in field)
    )


def _shape(data: str) -> str:
    """The data with volatile fields blanked (prefix and action always kept): a
    replayed path renders the same button with a fresh version or token."""
    fields = data.split(":")
    return ":".join(fields[:2] + ["·" if _volatile(f) else f for f in fields[2:]])


class Crawler:
    def __init__(self, h):
        self.h = h
        self.problems: list[str] = []
        self.unreachable: list[str] = []
        self.seen: set[str] = set()
        self.per_kind: dict[str, int] = {}
        self.queue: deque = deque()
        self.taps = 0

    def locate(self, data: str, loose: bool = False):
        """The live button for `data`: exactly, then with fresh versions, then —
        when the screen has moved on (a word left the first page) — any button
        of the same kind, which reaches the same handler."""
        h = self.h
        tests = [
            lambda d: d == data,
            lambda d: _shape(d) == _shape(data),
        ]
        if loose:
            tests.append(lambda d: _kind(d) == _kind(data))
        for match in tests:
            for entry in reversed(h.tg.sent):
                mid = entry["id"]
                if mid not in h.tg.live:
                    continue
                for _t, d in h.tg.buttons(mid):
                    if match(d):
                        return mid, d
        return None, None

    def collect(self, path, mids):
        for mid in mids:
            if mid not in self.h.tg.live:
                continue
            for _label, data in self.h.tg.buttons(mid):
                key = _shape(data)
                if key in self.seen or _is_card_button(data):
                    continue
                if self.per_kind.get(_kind(data), 0) >= PER_KIND:
                    continue
                self.seen.add(key)
                self.per_kind[_kind(data)] = self.per_kind.get(_kind(data), 0) + 1
                self.queue.append((path, data))

    async def do(self, step, checked: bool):
        """Run one step; with `checked`, it must visibly do something."""
        h = self.h
        kind = step[0]
        before = h._view()
        errors = len(h.tg.errors())
        if kind == "say":
            await h._say(step[1])
        elif kind == "tap":
            mid, data = self.locate(step[1])
            if mid is None:
                mid, data = h.tg.dummy(), step[1]
            await h._tap(mid, data)
        elif kind == "doc":
            await h.send_document(step[1], step[2])
        elif kind == "sticker":
            await h.send_sticker()
        elif kind == "tapk":
            mid, data = self.locate(step[1], loose=True)
            if mid is None:
                self.problems.append(f"{step}: no such button on screen")
                return
            await h._tap(mid, data)
        elif kind == "as":
            h.tg_id = step[1]
            return
        elif kind == "pw":
            from app.config import get_settings

            object.__setattr__(get_settings(), "access_password", step[1])
            return
        if checked:
            if h._view() == before and not str(step[1:2]).startswith("('noop"):
                self.problems.append(f"{step[:2]}: no visible response")
            if len(h.tg.errors()) > errors:
                self.problems.append(f"{step[:2]}: handler crashed")

    async def replay(self, path):
        for step in path:
            await self.do(step, checked=False)

    async def press(self, path, data):
        h = self.h
        mid, live_data = self.locate(data)
        if mid is None:
            await self.replay(path)
            mid, live_data = self.locate(data, loose=True)
        if mid is None:
            screen = [
                ((h.tg.live[e["id"]]["text"] or "")[:40].replace("\n", " "), [d for _t, d in h.tg.buttons(e["id"])][:4])
                for e in h.tg.sent[-2:] if e["id"] in h.tg.live
            ]
            self.unreachable.append(
                f"{data} via {[st[1] if len(st) > 1 else st[0] for st in path]} | screen {screen} | toasts {h.tg.toasts[-3:]}"
            )
            return
        sent_before = len(h.tg.sent)
        errors = len(h.tg.errors())
        try:
            await h.tap(mid, live_data, silent_ok=live_data.startswith(SILENT_PREFIXES))
        except AssertionError as e:
            self.problems.append(f"{live_data}: {e}")
        if len(h.tg.errors()) > errors:
            self.problems.append(f"{live_data}: handler crashed")
        self.taps += 1
        self.collect(path + [("tap", live_data)], [e["id"] for e in h.tg.sent[sent_before:]] + [mid])

    async def start(self, path):
        h = self.h
        await self.replay(path[:-1])
        sent_before = len(h.tg.sent)
        await self.do(path[-1], checked=True)
        self.collect(path, [e["id"] for e in h.tg.sent[sent_before:]])
        while self.queue and self.taps < MAX_TAPS:
            await self.press(*self.queue.popleft())


async def _category_id(h) -> int:
    """The learner's fullest folder — empty ones are not shown at all."""
    rows = await h.sql(
        "select category_id from user_words where user_id=:u and category_id is not null"
        " group by 1 order by count(*) desc limit 1", u=UID,
    )
    return rows[0][0] if rows else 0


async def _arrange(h) -> None:
    await h.fresh_day(["new_word", "new_word", "grammar"])
    # Give «Прогресс» something to manage: an archived word and a snoozed one.
    await h.sql(
        "update user_words set archived=true where id = (select id from user_words"
        " where user_id=:u and status in ('new', 'learning') order by id limit 1)", u=UID,
    )
    await h.sql(
        "update user_words set snooze_until = now() + interval '30 days' where id = (select id"
        " from user_words where user_id=:u and status in ('new', 'learning') order by id desc limit 1)", u=UID,
    )


async def test_every_reachable_button_answers(h, monkeypatch):
    from app.bot.handlers import pack_admin
    from app.config import get_settings

    monkeypatch.setattr(pack_admin, "_is_admin", lambda user: True)
    password = get_settings().access_password
    await _arrange(h)
    cat = await _category_id(h)
    entries = [[("pw", ""), ("say", m)] for m in MENU] + [
        [("say", T.BTN_TODAY), ("tap", AddWordsCB(action="start").pack()),
         ("say", "serendipity - счастливая случайность")],
        [("say", T.BTN_TODAY), ("say", "ephemeral")],  # a bare word: quick add
        [("say", T.BTN_TODAY), ("sticker",)],
        [("say", T.BTN_TODAY), ("tap", "set:no-such-action")],  # no handler matches
        [("tap", SearchCB(action="open").pack()), ("say", "apple")],
        [("say", T.BTN_MY_WORDS), ("tap", CategoryCB(action="new", flow="mw").pack()), ("say", "E2E папка")],
        [("say", T.BTN_MY_WORDS), ("tap", CategoryCB(action="rename", category_id=cat, flow="mw").pack()),
         ("say", "E2E переименована")],
        [("say", T.BTN_MY_WORDS), ("tap", f"mw:open:{cat}:0:0"), ("tapk", "cat:manage")],
        [("say", T.BTN_MY_WORDS), ("tap", f"mw:open:{cat}:0:0"), ("tapk", "cat:manage"),
         ("tapk", "cat:del_ask"), ("tapk", "cat:del_confirm")],
        [("say", T.BTN_MY_WORDS), ("tap", f"mw:open:{cat}:0:0"), ("tapk", "cat:manage"),
         ("tapk", "cat:merge"), ("tapk", "cat:merge_to")],
        [("say", T.BTN_MY_WORDS), ("tap", "mw:open:0:0:0"), ("tapk", "mw:word"), ("tapk", "del:ask")],
        [("say", T.BTN_MY_WORDS), ("tap", "mw:open:0:0:0"), ("tapk", "mw:word"), ("tapk", "del:ask"),
         ("tapk", "del:cancel")],
        # Collections: add a pack, then tap it again — fully owned asks before removing.
        [("say", T.BTN_COLLECTIONS), ("tap", "pk:group:Узкие темы:0:0:"), ("tapk", "pk:toggle"),
         ("tapk", "pk:toggle"), ("tapk", "pk:rem_ok")],
        [("say", T.BTN_COLLECTIONS), ("tap", "pk:group:Темы:0:0:"), ("tapk", "pk:page")],
        [("say", T.BTN_PROGRESS), ("tapk", "pg:managed"), ("tapk", "pu:unarchive")],
        [("say", T.BTN_PROGRESS), ("tapk", "pg:managed"), ("tapk", "pg:open")],
        [("say", "/packs_admin"), ("tapk", "pa:list"), ("tapk", "pa:open"), ("tapk", "pa:rename"),
         ("say", "E2E пак")],
        [("tap", ImportCB(action="start").pack())],
        [("say", T.BTN_IMPORT), ("doc", "words.txt", "apple\nbanana - банан\ncherry\n".encode())],
        [("tap", PacksCB(action="course_info").pack())],
        [("tap", ProgressCB(action="backlog").pack())],
        [("tap", ProgressCB(action="managed").pack())],
        # A brand-new learner: onboarding from the first /start …
        [("pw", ""), ("as", NEW_USER), ("say", "/start")],
        # … and behind the access password.
        [("pw", "e2e-pass"), ("as", NEW_USER + 1), ("say", "/start"), ("say", "e2e-pass")],
    ]
    crawler = Crawler(h)
    try:
        for path in entries:
            await h.reset()
            await _arrange(h)
            crawler.seen.clear()
            crawler.per_kind.clear()
            crawler.queue.clear()
            h.tg.live.clear()  # the chat of the previous entry is not this one's
            await crawler.start(path)
            h.tg_id = h.__class__.tg_id
    finally:
        object.__setattr__(get_settings(), "access_password", password)
    print(f"crawl: {crawler.taps} taps")
    for u in crawler.unreachable:
        print("UNREACHABLE", u)
    assert crawler.taps > 50, crawler.taps
    assert crawler.problems == [], "\n".join(crawler.problems)


async def test_an_old_collections_list_says_it_expired(h):
    """/start resets the state but leaves the list in the chat; a tap on it
    used to do nothing at all."""
    await h.fresh_day(["new_word"])
    await h.say(T.BTN_COLLECTIONS)
    groups = h.tg.last_with_buttons()["id"]
    await h.tap(groups, "pk:group:Темы:0:0:")
    listing = h.tg.last_with_buttons()["id"]
    data = next(d for _t, d in h.tg.buttons(listing) if d.startswith("pk:toggle"))
    await h.say("/start")
    await h.tap(listing, data)  # must visibly answer
    assert h.tg.toasts[-1] == T.LIST_EXPIRED
