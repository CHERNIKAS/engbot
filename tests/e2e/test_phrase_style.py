"""A phrase's neutral and colloquial renderings — and the learner's choice.

The owner, 2026-10-06: «Can you repeat that?» or «Come again?» — show both,
ask which to learn.
"""
from __future__ import annotations

from app.bot.texts import PHRASE_STYLE_SETTINGS
from app.services import push_service as ps
from tests.e2e.harness import UID, action_of

PHRASE = "Could you repeat that?"
CASUAL = "Come again?"


def _card_type(monkeypatch, ctype: str) -> None:
    monkeypatch.setattr(ps.PushService, "_card_type", lambda self, uw, word, user_level=None: ctype)


async def _next_phrase_is_ours(h, style=None) -> int:
    """Make «Could you repeat that?» the next new phrase; return its user_word id."""
    await h.fresh_day(["phrase", "phrase"])
    await h.sql(
        "update user_words set status='mastered' where user_id=:u and word_id in"
        " (select id from words where is_phrase)", u=UID,
    )
    (uw_id,), = await h.sql(
        "select uw.id from user_words uw join words w on w.id = uw.word_id"
        " where uw.user_id=:u and w.writing=:p", u=UID, p=PHRASE,
    )
    await h.sql("update user_words set status='new', phrase_style=:s where id=:i", s=style, i=uw_id)
    return uw_id


async def _choose(h, idx: int) -> None:
    question = h.tg.last_with_buttons()
    assert "Какой вариант учить" in question["text"]
    await h.act(question["id"], "style", idx)


async def test_a_new_colloquial_phrase_asks_which_to_learn_then_teaches_it(h, monkeypatch):
    _card_type(monkeypatch, ps.CARD_REVERSE)
    uw_id = await _next_phrase_is_ours(h)
    await h.tick()
    st = await h.state()
    assert st["inflight"]["kind"] == "style"
    assert CASUAL in h.tg.last_with_buttons()["text"]
    await _choose(h, 1)  # casual
    card = (await h.state())["inflight"]
    assert card["kind"] == "word" and card["id"] == uw_id
    assert card["correct"] == CASUAL
    # Wrong options are phrases too — nothing to guess from the shape.
    assert all(len(o.split()) >= 2 for o in card["options"]), card["options"]
    assert (await h.sql("select phrase_style from user_words where id=:i", i=uw_id))[0][0] == "casual"
    await h.tap_text(card["msg_id"], CASUAL)
    assert "Нейтрально" in h.tg.live[card["msg_id"]]["text"]
    assert await h.done_kinds() == ["phrase"]
    await h.check_invariants()


async def test_the_other_rendering_typed_is_right_too(h, monkeypatch):
    _card_type(monkeypatch, ps.CARD_TYPE_IN)
    await _next_phrase_is_ours(h, style="neutral")
    card = await h.card()
    assert card["correct"] == PHRASE
    await h.say(CASUAL)
    assert (await h.state())["inflight"] is None
    rows = await h.sql(
        "select result from word_reviews where user_id=:u and user_word_id=:i order by id desc limit 1",
        u=UID, i=card["id"],
    )
    assert rows[0][0] == "correct"
    await h.check_invariants()


async def test_a_neutral_learner_is_shown_the_colloquial_one(h, monkeypatch):
    _card_type(monkeypatch, ps.CARD_RECOGNITION)
    await _next_phrase_is_ours(h, style="neutral")
    card = await h.card()
    await h.tap_text(card["msg_id"], card["correct"])
    assert f"Ещё говорят: <b>{CASUAL}</b>" in h.tg.live[card["msg_id"]]["text"]
    await h.check_invariants()


async def test_a_default_style_in_settings_skips_the_question(h, monkeypatch):
    _card_type(monkeypatch, ps.CARD_RECOGNITION)
    uw_id = await _next_phrase_is_ours(h)
    await h.sql(
        "update user_tracks set settings = settings || '{\"phrase_style\": \"both\"}'::jsonb where user_id=:u",
        u=UID,
    )
    await h.tick()
    assert (await h.state())["inflight"]["kind"] == "word"
    assert (await h.sql("select phrase_style from user_words where id=:i", i=uw_id))[0][0] == "both"
    await h.check_invariants()


async def test_style_can_be_changed_from_my_words(h):
    uw_id = await _next_phrase_is_ours(h, style="neutral")
    await h.tap(h.tg.dummy(), f"pu:style_ask:{uw_id}:0:0")
    question = h.tg.last_with_buttons()
    assert "Какой вариант учить" in question["text"]
    await h.act(question["id"], "style", 2)  # both
    assert (await h.sql("select phrase_style from user_words where id=:i", i=uw_id))[0][0] == "both"
    await h.check_invariants()


async def test_the_settings_screen_sets_the_default(h):
    await h.fresh_day(["new_word"])
    await h.say("⚙️ Настройки")
    settings = h.tg.last_with_buttons()["id"]
    style = next(d for _t, d in h.tg.buttons(settings) if d.startswith("set:style_open"))
    await h.tap(settings, style)
    assert h.tg.live[settings]["text"].startswith("🗣")
    casual = next(d for _t, d in h.tg.buttons(settings) if d.startswith("set:style_set") and "casual" in d)
    await h.tap(settings, casual)
    rows = await h.sql("select settings->>'phrase_style' from user_tracks where user_id=:u and track='en'", u=UID)
    assert rows[0][0] == "casual"
    await h.check_invariants()
