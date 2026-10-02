"""Every card the plan sends must still answer to its own buttons.

A sender has two jobs: put the card in the chat, and record it as in flight in
the state the tick saves. The second is invisible until it fails, and when it
fails the first keeps happening. The triage screen showed both halves on
2026-10-02: shadowing `state` made the write raise after the send, so nothing
was in flight — the next tick sent the screen again, every five minutes, and
each copy was dead on arrival, because a tap is checked against the inflight
that was never written.

The guards in test_plan_drives_push read source text and passed. These drive
`_serve` for each kind the plan composes, then tap the card that went out
through the same context check the real handler uses.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain import day_plan as plan_rules
from app.services import push_service as ps
from app.services.push_service import PushService

MSG_ID = 555
NOW = 1_000.0


class _User:
    id = 1
    telegram_id = 99
    level = "A1"


class _Query:
    """A tap on message `msg_id`. Records the toast a stale tap gets."""

    def __init__(self, msg_id: int):
        self.message = SimpleNamespace(message_id=msg_id)
        self.toasts: list = []

    async def answer(self, text=None, **kwargs):
        self.toasts.append(text)


class _UserWords:
    async def current_theme(self, user_id, track):
        return SimpleNamespace(id=7, title="🔢 Числа")

    async def theme_batch(self, user_id, track, theme_id, size):
        return [
            (SimpleNamespace(id=1), SimpleNamespace(writing="one", translation="один")),
            (SimpleNamespace(id=2), SimpleNamespace(writing="two", translation="два")),
        ]


_TOPIC = SimpleNamespace(id=3, title="Present Simple")
_PHRASE = SimpleNamespace(id=11)


class _ConstructorRepo:
    def __init__(self, session):
        pass

    async def due_test_topic(self, user_id):
        return _TOPIC

    async def state(self, user_id, topic_id):
        return None

    async def test_phrases(self, topic_id, limit, exclude=None):
        return [SimpleNamespace(id=21), SimpleNamespace(id=22)]

    async def get_phrase(self, phrase_id):
        return _PHRASE if phrase_id == _PHRASE.id else None


class _ConstructorService:
    def __init__(self, session):
        pass

    async def open_card(self, user_id, plan_done=0, plan_total=0):
        view = SimpleNamespace(
            typing=False, options=["work", "works"], phrase_id=_PHRASE.id,
            can_undo=False, text="He ___ here.",
        )
        return view, _PHRASE, _TOPIC


class _Session:
    async def get(self, model, pk):
        return _TOPIC if pk == _TOPIC.id else None


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(ps, "ConstructorRepository", _ConstructorRepo)
    monkeypatch.setattr(ps, "ConstructorService", _ConstructorService)

    svc = PushService.__new__(PushService)
    svc._session = _Session()
    svc._uw = _UserWords()
    svc.sent = []

    async def _raw_send(chat_id, text, kb=None, **kwargs):
        svc.sent.append(kwargs.get("kind", "unknown"))
        return MSG_ID

    svc._raw_send = _raw_send
    return svc


def _load_returning(state: dict):
    async def _load(user_id):
        return state

    return _load


async def _serve(svc, kind: str) -> dict:
    state = {"day": "2026-10-02", "next_ts": 0.0, "inflight": None}
    assert await svc._serve(_User(), None, kind, 0, 16, state, NOW), kind
    return state


@pytest.mark.asyncio
async def test_a_triage_screen_answers_its_own_buttons(service):
    state = await _serve(service, plan_rules.TRIAGE)
    assert len(service.sent) == 1
    service._load = _load_returning(state)

    query = _Query(MSG_ID)
    assert await service._triage_context(_User(), query) is not None
    assert query.toasts == []


@pytest.mark.asyncio
async def test_a_topic_test_offer_answers_its_own_buttons(service):
    state = await _serve(service, plan_rules.TEST)
    assert len(service.sent) == 1
    service._load = _load_returning(state)

    query = _Query(MSG_ID)
    assert await service._test_context(_User(), _TOPIC.id, query) is not None
    assert query.toasts == []


@pytest.mark.asyncio
async def test_a_constructor_card_answers_its_own_buttons(service):
    state = await _serve(service, plan_rules.GRAMMAR)
    assert len(service.sent) == 1
    service._load = _load_returning(state)

    query = _Query(MSG_ID)
    assert await service._constructor_context(_User(), _PHRASE.id, query) is not None
    assert query.toasts == []


@pytest.mark.parametrize("kind", [plan_rules.TRIAGE, plan_rules.TEST, plan_rules.GRAMMAR])
@pytest.mark.asyncio
async def test_a_tap_on_another_message_is_still_refused(service, kind):
    """The check the cards pass above is a real one: an older copy of the same
    card — what the learner was tapping all evening — is turned away."""
    state = await _serve(service, kind)
    service._load = _load_returning(state)

    query = _Query(MSG_ID - 1)
    if kind == plan_rules.TRIAGE:
        ctx = await service._triage_context(_User(), query)
    elif kind == plan_rules.TEST:
        ctx = await service._test_context(_User(), _TOPIC.id, query)
    else:
        ctx = await service._constructor_context(_User(), _PHRASE.id, query)
    assert ctx is None
    assert query.toasts


@pytest.mark.parametrize("kind", [plan_rules.TRIAGE, plan_rules.TEST, plan_rules.GRAMMAR])
@pytest.mark.asyncio
async def test_every_screen_is_logged_with_its_kind(service, kind):
    """Before the fix the triage screens logged as uid=null kind=unknown, so
    finding the duplicates to delete meant matching timestamps by hand."""
    await _serve(service, kind)
    assert service.sent and service.sent[0] != "unknown"
