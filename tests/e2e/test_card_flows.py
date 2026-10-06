"""Every card the plan sends, tapped the way a learner taps it.

Each test arranges a day, lets the real worker tick send a card, then drives the
real dispatcher with the buttons that card actually carries. Two things are
checked everywhere, on top of each scenario's own assertions:
- every tap visibly does something (harness.tap) — the «кнопка не отвечает»
  reports of 2026-10-02 were three different bugs with that one symptom;
- no handler crashes, and the card in flight is a message that exists.
"""
from __future__ import annotations

import asyncio

import pytest

from app.bot.texts import (
    BTN_LESSON,
    BTN_LESSON_END,
    BTN_TODAY,
    LESSON_DAY_DONE,
    LESSON_PING,
    PUSH_STALE,
    TODAY_DONE,
)
from app.services import push_service as ps
from tests.e2e.harness import TAPPED, UID, action_of


def _force_card_type(monkeypatch, ctype: str) -> None:
    monkeypatch.setattr(ps.PushService, "_card_type", lambda self, uw, word, user_level=None: ctype)


async def _card_of_type(h, monkeypatch, ctype: str, kinds=("new_word", "new_word")) -> dict:
    """A card of exactly this type. Cloze needs an example sentence and falls
    back to a choice card without one — by design — so redraw until the picked
    word supports it."""
    _force_card_type(monkeypatch, ctype)
    for _ in range(8):
        await h.fresh_day(list(kinds))
        h.tg.live.clear()
        card = await h.card()
        if card.get("ctype") == ctype:
            return card
    pytest.skip(f"no word in this copy renders as {ctype}")


async def _reviews(h) -> int:
    return (await h.sql("select count(*) from word_reviews where user_id=:u", u=UID))[0][0]


async def _phrase_slots(h, phrase_id: int) -> list[dict]:
    return (await h.sql("select slots from grammar_phrases where id=:i", i=phrase_id))[0][0]


async def _phrase_en(h, phrase_id: int) -> str:
    return (await h.sql("select en from grammar_phrases where id=:i", i=phrase_id))[0][0]


async def _assisted(h) -> None:
    await h.sql("update user_grammar_topics set typing=false where user_id=:u", u=UID)


# ---- word cards ------------------------------------------------------------- #


@pytest.mark.parametrize("ctype", [ps.CARD_RECOGNITION, ps.CARD_REVERSE])
async def test_a_choice_card_answered_right(h, monkeypatch, ctype):
    _force_card_type(monkeypatch, ctype)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    before = await _reviews(h)
    await h.tap_text(card["msg_id"], card["correct"])
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["new_word"]
    assert await _reviews(h) == before + 1
    await h.check_invariants()


async def test_a_choice_card_answered_wrong(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    wrong = next(o for o in card["options"] if o != card["correct"])
    await h.tap_text(card["msg_id"], wrong)
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["new_word"]
    await h.check_invariants()


async def test_a_double_tap_on_an_answer_counts_once(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    data = h.data_for(card["msg_id"], card["correct"])
    before = await _reviews(h)
    await asyncio.gather(h._tap(card["msg_id"], data), h._tap(card["msg_id"], data), h._tap(card["msg_id"], data))
    assert await _reviews(h) == before + 1
    assert await h.done_kinds() == ["new_word"]
    await h.check_invariants()


@pytest.mark.parametrize("ctype", [ps.CARD_TYPE_IN, ps.CARD_CLOZE])
async def test_a_typed_card_answered_right(h, monkeypatch, ctype):
    card = await _card_of_type(h, monkeypatch, ctype)
    await h.say(card["correct"])
    assert (await h.state())["inflight"] is None, ctype
    assert await h.done_kinds() == ["new_word"]
    await h.check_invariants()


@pytest.mark.parametrize("ctype", [ps.CARD_TYPE_IN, ps.CARD_CLOZE])
async def test_a_typed_card_given_up(h, monkeypatch, ctype):
    card = await _card_of_type(h, monkeypatch, ctype)
    await h.act(card["msg_id"], "giveup")
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["new_word"]
    await h.check_invariants()


@pytest.mark.parametrize(
    "action, ctype",
    [("master", ps.CARD_RECOGNITION), ("hide", ps.CARD_RECOGNITION), ("snooze", ps.CARD_CLOZE)],
)
async def test_a_word_put_aside_frees_the_card_and_the_day_goes_on(h, monkeypatch, action, ctype):
    card = await _card_of_type(h, monkeypatch, ctype, kinds=("new_word", "new_word", "new_word"))
    await h.act(card["msg_id"], action)
    st = await h.state()
    assert st["inflight"] is None, action
    # The slot is used up — otherwise the next tick deals another word into the
    # same slot, forever (2026-10-04: fifteen «знаю» in an evening, plan frozen).
    assert await h.done_kinds() == ["new_word"], action
    await h.check_invariants()
    # Not stuck: the next tick brings a different card.
    st["next_ts"] = 0.0
    await h.put_state(st)
    nxt = await h.card()
    assert nxt["msg_id"] != card["msg_id"]
    await h.check_invariants()


async def _next_card(h) -> dict:
    st = await h.state()
    st["next_ts"] = 0.0
    await h.put_state(st)
    await h.tick()
    return (await h.state())["inflight"]


async def test_three_known_in_a_row_brings_a_screen_to_mark_in_bulk(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word"] * 6)
    known = []
    card = await h.card()
    for _ in range(3):
        assert card["kind"] == "word"
        known.append(card["id"])
        await h.act(card["msg_id"], "master")
        card = (await h.state())["inflight"] or await _next_card(h)
    screen = (await h.state())["inflight"]
    assert screen["kind"] == "triage" and screen["source"] == "frequency", screen
    assert "многое уже знаешь" in h.tg.live[screen["msg_id"]]["text"]
    assert not {r[0] for r in screen["rows"]} & set(known)
    assert await h.done_kinds() == ["new_word"] * 3  # the three, not the screen
    # Knows all of it: the next screen of the same stream follows.
    for i in range(len(screen["rows"])):
        await h.act(screen["msg_id"], "trg", i)
    await h.act(screen["msg_id"], "trgok")
    nxt = (await h.state())["inflight"]
    assert nxt and nxt["kind"] == "triage" and nxt["source"] == "frequency"
    assert await h.done_kinds() == ["new_word"] * 3  # bulk screens take no slot
    await h.check_invariants()


async def test_an_answered_card_breaks_the_known_streak(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word"] * 6)
    card = await h.card()
    for step in ("master", "master", "answer", "master"):
        if step == "answer":
            await h.tap_text(card["msg_id"], card["correct"])
        else:
            await h.act(card["msg_id"], "master")
        card = await _next_card(h)
    assert card["kind"] == "word"  # no screen: the streak was broken
    await h.check_invariants()


async def test_legacy_know_button_still_answers(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    await h.tap(card["msg_id"], f"pu:know:{card['id']}:0:0")
    assert (await h.state())["inflight"] is None
    await h.check_invariants()


@pytest.mark.parametrize("choice", ["leech_park", "leech_keep"])
async def test_a_leech_prompt_answers_both_ways(h, monkeypatch, choice):
    # Only a word still being learned can become a leech; mastered ones ride a
    # score instead (_leech_after).
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    await h.sql(
        "update user_words set consecutive_wrong = :n where id = :i", n=ps.LEECH_THRESHOLD - 1, i=card["id"]
    )
    wrong = next(o for o in card["options"] if o != card["correct"])
    await h.tap_text(card["msg_id"], wrong)
    prompt = h.tg.last_with_buttons()
    assert any(action_of(d) == choice for _t, d in h.tg.buttons(prompt["id"])), "no leech prompt"
    await h.act(prompt["id"], choice)
    await h.check_invariants()


# ---- the constructor -------------------------------------------------------- #


async def _constructor(h) -> dict:
    await _assisted(h)
    await h.fresh_day(["grammar", "grammar"])
    card = await h.card()
    assert card["kind"] == "phrase"
    return card


async def test_a_constructor_sentence_built_right(h):
    card = await _constructor(h)
    for slot in await _phrase_slots(h, card["id"]):
        await h.tap_text(card["msg_id"], slot["correct"])
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["grammar"]
    await h.check_invariants()


async def test_grammar_answers_count_toward_the_daily_pace(h):
    """A day of grammar is not a day off: the pace that sizes the word pool
    counts constructor sentences as well as word cards."""
    from app.infrastructure.repositories.reviews import WordReviewRepository

    async def pace() -> float:
        async with h.sm() as session:
            return await WordReviewRepository(session).typical_daily_answers(UID, ps._TRACK, days=1) or 0.0

    await h.sql("delete from word_reviews where user_id=:u", u=UID)
    before = await pace()
    card = await _constructor(h)
    for slot in await _phrase_slots(h, card["id"]):
        await h.tap_text(card["msg_id"], slot["correct"])
    assert await pace() == before + 1
    await h.check_invariants()


async def test_every_wrong_constructor_tap_is_visible_until_attempts_run_out(h):
    card = await _constructor(h)
    slot0 = (await _phrase_slots(h, card["id"]))[0]
    wrong = next(o for o in slot0["options"] if o != slot0["correct"])
    for _ in range(ps.ctor.MAX_ATTEMPTS):
        await h.tap_text(card["msg_id"], wrong)  # asserts a visible response each time
    # Attempts gone: the card settles instead of waiting forever.
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["grammar"]
    await h.check_invariants()


async def test_constructor_undo_hint_and_rule(h):
    card = await _constructor(h)
    slots = await _phrase_slots(h, card["id"])
    mid = card["msg_id"]
    await h.tap_text(mid, slots[0]["correct"])
    await h.act(mid, "pundo")
    assert list((await h.state())["inflight"]["state"]["chosen"]) == []
    await h.act(mid, "prule")
    await h.act(mid, "prule")  # folds back
    await h.act(mid, "phint")
    await h.check_invariants()
    # The hint may already have placed a piece; carry on from where the card is.
    while (st := (await h.state())["inflight"]) is not None:
        await h.tap_text(mid, slots[len(st["state"]["chosen"])]["correct"])
    assert (await h.state())["inflight"] is None
    await h.check_invariants()


async def test_constructor_give_up(h):
    # «Сдаться» is offered once the learner types; the assisted card has none.
    await h.sql("update user_grammar_topics set typing=true where user_id=:u", u=UID)
    await h.fresh_day(["grammar", "grammar"])
    card = await h.card()
    await h.act(card["msg_id"], "pgiveup")
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["grammar"]
    await _assisted(h)
    await h.check_invariants()


async def test_the_rule_stays_open_while_the_learner_builds(h):
    card = await _constructor(h)
    slots = await _phrase_slots(h, card["id"])
    mid = card["msg_id"]
    await h.act(mid, "prule")
    opened = h.tg.live[mid]["text"]
    await h.tap_text(mid, slots[0]["correct"])
    assert len(h.tg.live[mid]["text"]) > len(opened) - 5, "the rule folded away on a slot tap"
    await h.act(mid, "prule")
    assert len(h.tg.live[mid]["text"]) < len(opened)
    await h.check_invariants()


async def test_fast_constructor_taps_are_applied_in_order(h):
    """The 21:15 report: taps racing each other. Under the lock they queue."""
    card = await _constructor(h)
    slots = await _phrase_slots(h, card["id"])
    first = h.data_for(card["msg_id"], slots[0]["correct"])
    await asyncio.gather(*(h._tap(card["msg_id"], first) for _ in range(3)))
    st = (await h.state())["inflight"]
    # First tap fills slot 0; the same button data replayed on later slots is
    # just an option index, judged against whatever slot is current — but the
    # state must be one coherent card, not a mix of three.
    assert st is None or len(st["state"]["chosen"]) + (st["state"]["attempt"] - 1) == 3
    await h.check_invariants()


async def test_typing_mode_takes_a_right_answer_after_a_wrong_one(h):
    """2026-10-06: a wrong typed answer claimed the card for ten minutes, and
    the right one typed next was swallowed in silence — the chat «froze»."""
    await h.sql("update user_grammar_topics set typing=true where user_id=:u", u=UID)
    await h.fresh_day(["grammar", "grammar"])
    card = await h.card()
    await h.say("definitely not it")
    st = (await h.state())["inflight"]
    assert st and st["state"]["attempt"] == 2  # a miss, the card still open
    await h.say(await _phrase_en(h, card["id"]))
    assert (await h.state())["inflight"] is None, "the right answer after a miss was ignored"
    assert await h.done_kinds() == ["grammar"]
    await _assisted(h)
    await h.check_invariants()


async def test_typing_mode_runs_out_of_attempts_and_settles(h):
    await h.sql("update user_grammar_topics set typing=true where user_id=:u", u=UID)
    await h.fresh_day(["grammar", "grammar"])
    await h.card()
    for _ in range(3):
        await h.say("still not it")
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["grammar"]
    await _assisted(h)
    await h.check_invariants()


async def test_a_second_hint_in_typing_mode_says_so(h):
    await h.sql("update user_grammar_topics set typing=true where user_id=:u", u=UID)
    await h.fresh_day(["grammar", "grammar"])
    card = await h.card()
    await h.act(card["msg_id"], "phint")
    await h.act(card["msg_id"], "phint")  # must visibly respond
    assert "Начало уже открыто" in (h.tg.toasts[-1] or "")
    await _assisted(h)
    await h.check_invariants()


async def test_constructor_typing_mode(h):
    await h.sql("update user_grammar_topics set typing=true where user_id=:u", u=UID)
    await h.fresh_day(["grammar", "grammar"])
    card = await h.card()
    await h.say(await _phrase_en(h, card["id"]))
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["grammar"]
    await _assisted(h)
    await h.check_invariants()


# ---- triage ----------------------------------------------------------------- #


async def test_triage_marks_and_settles_once(h):
    await h.fresh_day(["triage", "new_word"])
    card = await h.card()
    assert card["kind"] == "triage"
    mid = card["msg_id"]
    rows = card["rows"]
    await h.act(mid, "trg", 0)
    await h.act(mid, "trg", 1)
    await h.act(mid, "trg", 1)  # untoggle
    done = h.data_by_action(mid, "trgok")
    await asyncio.gather(h._tap(mid, done), h._tap(mid, done))
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["triage"]
    status = (await h.sql("select status from user_words where id=:i", i=rows[0][0]))[0][0]
    assert status == "mastered"
    await h.check_invariants()


async def test_knowing_a_whole_screen_brings_the_next_one(h):
    await h.fresh_day(["triage", "new_word"])
    card = await h.card()
    mid = card["msg_id"]
    for i in range(len(card["rows"])):
        await h.act(mid, "trg", i)
    await h.act(mid, "trgok")
    nxt = (await h.state())["inflight"]
    assert nxt and nxt["kind"] == "triage" and nxt["msg_id"] != mid, "no second screen"
    assert not {r[0] for r in nxt["rows"]} & {r[0] for r in card["rows"]}
    assert await h.done_kinds() == ["triage"]  # still one slot; the extra screen is a bonus
    # Knowing little of the next one ends the run.
    await h.act(nxt["msg_id"], "trg", 0)
    await h.act(nxt["msg_id"], "trgok")
    assert (await h.state())["inflight"] is None
    await h.check_invariants()


# ---- the topic check -------------------------------------------------------- #


async def _due_test(h) -> None:
    await h.sql(
        "update user_grammar_topics set passed_at = now() - interval '10 days',"
        " test_due_at = now() - interval '1 day' where user_id=:u and topic_id=1",
        u=UID,
    )


async def test_topic_check_run_to_the_end(h):
    await _due_test(h)
    await h.fresh_day(["test", "new_word"])
    card = await h.card()
    assert card["kind"] == "test"
    await h.act(card["msg_id"], "tstart")
    for pid in card["phrases"]:
        await h.say(await _phrase_en(h, pid))
    assert (await h.state())["inflight"] is None
    assert await h.done_kinds() == ["test"]
    await h.check_invariants()


async def test_topic_check_put_off(h):
    await _due_test(h)
    await h.fresh_day(["test", "new_word"])
    card = await h.card()
    await h.act(card["msg_id"], "tlater")
    assert (await h.state())["inflight"] is None
    await h.check_invariants()


# ---- rule cards ------------------------------------------------------------- #


async def test_a_new_topic_rule_card_is_acknowledged(h):
    await h.fresh_day(["new_word", "new_word"])
    await h.sql("update user_grammar_topics set rule_seen_at = null where user_id=:u and topic_id=1", u=UID)
    await h.tick()
    rule = h.tg.last_with_buttons()
    await h.act(rule["id"], "rule_ok")
    await h.check_invariants()


async def test_the_legacy_grammar_rule_button_answers(h):
    await h.fresh_day(["new_word"])
    rows = await h.sql("select id from user_grammar_items where user_id=:u limit 1", u=UID)
    if not rows:
        pytest.skip("no grammar items for the learner in this copy")
    sent = len(h.tg.sent)
    await h.tap(next(iter(h.tg.live), 0) or 1, f"pu:rule:{rows[0][0]}:0:0", silent_ok=True)
    assert h.tg.errors() == []


# ---- nudges and races ------------------------------------------------------- #


async def test_a_tap_on_a_replaced_card_says_so_and_the_new_one_works(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    card = await h.card()
    await h.patch_inflight(retry_ts=0)
    await h.tick()  # the nudge replaces the message
    new = (await h.state())["inflight"]
    assert new["msg_id"] != card["msg_id"] and card["msg_id"] in h.tg.deleted
    await h.tap(card["msg_id"], f"pu:ans:{card['id']}:0:0")
    assert h.tg.toasts[-1] == PUSH_STALE
    await h.tap_text(new["msg_id"], new["correct"])
    assert (await h.state())["inflight"] is None
    await h.check_invariants()


async def test_a_card_being_worked_is_not_replaced_by_a_nudge(h):
    card = await _constructor(h)
    slots = await _phrase_slots(h, card["id"])
    await h.tap_text(card["msg_id"], slots[0]["correct"])
    await h.patch_inflight(retry_ts=0)
    await h.tick()
    assert (await h.state())["inflight"]["msg_id"] == card["msg_id"]
    await h.check_invariants()


async def test_taps_racing_the_tick_leave_one_coherent_card(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    for _ in range(5):
        await h.fresh_day(["new_word", "new_word"])
        h.tg.live.clear()  # last round's card is not this round's chat
        card = await h.card()
        await h.patch_inflight(retry_ts=0)
        data = h.data_for(card["msg_id"], card["correct"])
        await asyncio.gather(h.tick(), h._tap(card["msg_id"], data))
        await h.check_invariants()
        answerable = [
            mid for mid in h.tg.live
            if any(action_of(d) == "ans" for _t, d in h.tg.buttons(mid))
        ]
        # Either the tap won (answered, nothing live) or the nudge won (one
        # fresh copy live, the old one gone) — never two cards at once.
        assert len(answerable) <= 1, answerable
        assert await h.done_kinds() in ([], ["new_word"])


# ---- lesson mode ------------------------------------------------------------ #


async def test_a_lesson_runs_cards_back_to_back_and_ends_on_the_button(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word", "new_word"])
    await h.say(BTN_LESSON)
    first = (await h.state())["inflight"]
    assert first, "the lesson did not serve a card"
    await h.tap_text(first["msg_id"], first["correct"])
    second = (await h.state())["inflight"]
    assert second and second["msg_id"] != first["msg_id"], "no next card without waiting for a tick"
    assert await h.tick() is False  # pushes stand aside
    await h.say(BTN_LESSON_END)
    st = await h.state()
    assert "lesson" not in st
    assert "пуш" in h.tg.sent[-1]["text"]
    await h.check_invariants()


async def test_a_lesson_that_finishes_the_plan_offers_more(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word"])
    await h.say(BTN_LESSON)
    card = (await h.state())["inflight"]
    await h.tap_text(card["msg_id"], card["correct"])
    offer = h.tg.last_with_buttons()
    assert "Хочешь ещё" in offer["text"]
    assert "lesson" in await h.state()  # waiting for the choice
    # Practice: a card at once, then another after answering it.
    await h.act(offer["id"], "practice")
    first = (await h.state())["inflight"]
    assert first and first.get("extra") == "practice"
    await h.tap_text(first["msg_id"], first["correct"])
    second = (await h.state())["inflight"]
    assert second and second["msg_id"] != first["msg_id"] and second["id"] != first["id"]
    assert await h.plan() == []  # practice never opens a plan
    await h.say(BTN_TODAY)
    assert h.tg.sent[-1]["text"] == TODAY_DONE
    await h.say(BTN_LESSON_END)
    assert "lesson" not in await h.state() and "extra" not in await h.state()
    await h.check_invariants()


def _pool_room(monkeypatch, room: int, active: int) -> None:
    from app.services.backlog_service import BacklogService

    async def fake(self, user_id, track):
        return room, active

    monkeypatch.setattr(BacklogService, "room", fake)


async def test_more_new_words_after_the_plan_then_the_offer_again(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    monkeypatch.setattr(ps, "EXTRA_NEW_WORDS", 2)
    _pool_room(monkeypatch, room=10, active=3)
    await h.fresh_day(["new_word"])
    await h.say(BTN_LESSON)
    card = (await h.state())["inflight"]
    await h.tap_text(card["msg_id"], card["correct"])
    await h.act(h.tg.last_with_buttons()["id"], "more")
    for _ in range(2):
        nxt = (await h.state())["inflight"]
        assert nxt and nxt.get("extra") == "new", "no extra new word"
        await h.tap_text(nxt["msg_id"], nxt["correct"])
    # Two given: the choice comes back instead of a third.
    assert (await h.state())["inflight"] is None
    assert "Хочешь ещё" in h.tg.last_with_buttons()["text"]
    await h.act(h.tg.last_with_buttons()["id"], "enough")
    assert "lesson" not in await h.state()
    await h.check_invariants()


async def test_no_new_words_offered_when_the_pool_is_full(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    _pool_room(monkeypatch, room=0, active=13)
    await h.fresh_day(["new_word"])
    await h.say(BTN_LESSON)
    card = (await h.state())["inflight"]
    await h.tap_text(card["msg_id"], card["correct"])
    offer = h.tg.last_with_buttons()
    assert "13 слов в работе" in offer["text"]
    assert not any(action_of(d) == "more" for _t, d in h.tg.buttons(offer["id"]))
    # A stale «➕» from an older offer is still answered honestly.
    await h.tap(offer["id"], "pu:more:0:0:0")
    assert "слов в работе" in (h.tg.toasts[-1] or "")
    await h.check_invariants()


async def test_after_the_plan_by_push_practice_runs_until_ignored(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word"])
    card = await h.card()
    await h.tap_text(card["msg_id"], card["correct"])
    st = await h.state()
    st["next_ts"] = 0.0
    await h.put_state(st)
    await h.tick()  # closes the day: summary + offer
    offer = h.tg.last_with_buttons()
    assert "Хочешь ещё" in offer["text"]
    await h.act(offer["id"], "practice")
    first = (await h.state())["inflight"]
    assert first and first.get("extra") == "practice"
    # Ignored past the nudges: practice stops, the evening goes quiet.
    for _ in range(ps.PUSH_MAX_ATTEMPTS + 1):
        await h.patch_inflight(retry_ts=0)
        await h.tick()
    st = await h.state()
    assert st["inflight"] is None and "extra" not in st
    st["next_ts"] = 0.0
    await h.put_state(st)
    assert await h.tick() is False
    await h.check_invariants()


async def test_back_in_a_lesson_after_the_plan_gets_the_offer(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word"])
    card = await h.card()
    await h.tap_text(card["msg_id"], card["correct"])
    st = await h.state()
    st["next_ts"] = 0.0
    await h.put_state(st)
    await h.tick()
    await h.say(BTN_LESSON)
    assert "Хочешь ещё" in h.tg.last_with_buttons()["text"]
    await h.act(h.tg.last_with_buttons()["id"], "practice")
    assert ((await h.state())["inflight"] or {}).get("extra") == "practice"
    await h.check_invariants()


async def test_a_silent_lesson_asks_then_hands_back_to_pushes(h, monkeypatch):
    _force_card_type(monkeypatch, ps.CARD_RECOGNITION)
    await h.fresh_day(["new_word", "new_word"])
    await h.say(BTN_LESSON)
    st = await h.state()
    st["lesson"]["active_ts"] -= ps.LESSON_IDLE_SECONDS + 1
    await h.put_state(st)
    await h.run_lessons()
    ping = h.tg.last_with_buttons()
    assert ping["text"] == LESSON_PING
    await h.act(ping["id"], "here")
    assert ping["id"] in h.tg.deleted
    st = await h.state()
    assert "ping_ts" not in st["lesson"]
    st["lesson"]["active_ts"] -= ps.LESSON_IDLE_SECONDS + 1
    await h.put_state(st)
    await h.run_lessons()  # asks again
    st = await h.state()
    st["lesson"]["ping_ts"] -= ps.LESSON_PING_TIMEOUT_SECONDS + 1
    await h.put_state(st)
    await h.run_lessons()
    st = await h.state()
    assert "lesson" not in st and st["inflight"] is not None  # the card waits for pushes
    await h.check_invariants()


# ---- coverage --------------------------------------------------------------- #


def test_zz_every_push_button_action_was_tapped():
    """A button added later without a scenario here is a button nobody pressed
    before a learner did."""
    import re
    from pathlib import Path

    src = Path("app/bot/handlers/push.py").read_text(encoding="utf-8")
    actions = set(re.findall(r'F\.action == "([a-z_]+)"', src))
    assert actions - TAPPED == set()
