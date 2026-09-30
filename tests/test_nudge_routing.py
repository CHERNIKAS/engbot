"""A nudge must re-send the card that is actually in flight.

The bug this exists for: `_send_card` builds a word card for every kind except
grammar, and the nudge path called it for all of them. A constructor card in
flight carries a `grammar_phrases` id, so the nudge looked that number up in
`user_words` — where it belongs to somebody else. On production, user 2's nudges
for phrase 1 rendered `borrow`, which is user 1's word.

`test_every_plan_slot_kind_can_actually_be_served` did not catch it because the
send succeeded: a card went out, it was simply the wrong card, for the wrong
person. So this file checks the shape of what goes out, per kind, and fails on
any kind nobody has taught the nudge path about — including kinds added later.
"""
from __future__ import annotations

import pytest

from app.domain import day_plan as plan_rules
from app.services.push_service import PushService


class _Recorder:
    """Captures what the nudge decided to send instead of sending it."""

    def __init__(self):
        self.word_calls: list[tuple] = []
        self.constructor_calls: list[dict] = []
        self.skipped: list[str] = []


def _service(rec: _Recorder):
    service = PushService.__new__(PushService)

    async def _send_card(user, kind, item_id, **kwargs):
        rec.word_calls.append((kind, item_id, kwargs.get("prefix", "")))
        return 555, None, None

    async def _renudge_constructor(user, inflight, attempts, now_ts):
        rec.constructor_calls.append(dict(inflight))
        return 777

    service._send_card = _send_card
    service._renudge_constructor = _renudge_constructor
    return service


class _User:
    id = 2
    telegram_id = 99
    level = "A1"


@pytest.mark.asyncio
async def test_a_word_nudge_still_goes_through_the_word_sender():
    rec = _Recorder()
    inflight = {"kind": "word", "id": 42, "msg_id": 10}
    assert await _service(rec)._renudge(_User(), inflight, 1, 0.0) == 555
    assert rec.word_calls and rec.word_calls[0][0] == "word"
    assert rec.word_calls[0][1] == 42


@pytest.mark.asyncio
async def test_a_grammar_nudge_still_goes_through_the_word_sender():
    """Grammar is word-shaped — `_build_grammar` handles it inside the same
    sender — so it is the one other kind allowed down that path."""
    rec = _Recorder()
    inflight = {"kind": "grammar", "id": 7, "msg_id": 10}
    assert await _service(rec)._renudge(_User(), inflight, 1, 0.0) == 555
    assert rec.word_calls[0][0] == "grammar"


@pytest.mark.asyncio
async def test_a_constructor_nudge_never_reaches_the_word_sender():
    """The whole bug in one test. `id` here is a phrase id; sending it to the
    word sender is what rendered a stranger's vocabulary."""
    rec = _Recorder()
    inflight = {"kind": "phrase", "id": 1, "topic_id": 3, "msg_id": 10, "state": {}}
    assert await _service(rec)._renudge(_User(), inflight, 2, 0.0) == 777
    assert rec.word_calls == [], "конструктор ушёл в словарный отправитель"
    assert rec.constructor_calls[0]["id"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["triage", "test"])
async def test_offer_kinds_are_not_re_rendered_as_words(kind):
    """Triage and the topic check are offers. Whatever the nudge does with them,
    it must not be "look the id up in user_words"."""
    rec = _Recorder()
    inflight = {"kind": kind, "id": 5, "topic_id": 3, "msg_id": 10}
    result = await _service(rec)._renudge(_User(), inflight, 1, 0.0)
    assert rec.word_calls == [], f"{kind} ушёл в словарный отправитель"
    assert result == 10, "сообщение в полёте должно остаться прежним"


@pytest.mark.asyncio
async def test_every_kind_the_plan_can_produce_is_known_to_the_nudge_path():
    """The guard against the next version of this bug: a kind added to the plan
    without teaching the nudge path about it used to silently become a word
    card. Any kind not covered above has to show up here as a failure."""
    rec = _Recorder()
    service = _service(rec)
    handled = {"word", "grammar", "phrase", "triage", "test"}
    for kind in (
        plan_rules.REPEAT, plan_rules.GRAMMAR, plan_rules.PHRASE,
        plan_rules.NEW_WORD, plan_rules.NEW_THEME_WORD,
        plan_rules.TRIAGE, plan_rules.TEST,
    ):
        # Plan slot kinds map onto inflight kinds; the ones that do not are
        # served as words and carry `kind="word"` in flight.
        assert kind in handled or kind in {
            plan_rules.REPEAT, plan_rules.NEW_WORD, plan_rules.NEW_THEME_WORD,
        }, f"вид {kind} неизвестен пути напоминаний"

    # And a kind nobody taught it about must not quietly become a word card.
    rec2 = _Recorder()
    inflight = {"kind": "something_new", "id": 1, "msg_id": 10}
    await _service(rec2)._renudge(_User(), inflight, 1, 0.0)
    assert rec2.word_calls == [], "неизвестный вид превратился в словарную карточку"
