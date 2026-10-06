"""The after-plan features, at the points the flow tests do not pin down."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.bot.texts import BTN_LESSON, EXTRA_NOTHING_TO_PRACTISE
from app.services import push_service as ps
from tests.e2e.harness import UID


def _recognition(monkeypatch):
    monkeypatch.setattr(ps.PushService, "_card_type", lambda self, uw, word, user_level=None: ps.CARD_RECOGNITION)


async def _close_plan_by_push(h) -> dict:
    card = await h.card()
    await h.tap_text(card["msg_id"], card["correct"])
    st = await h.state()
    st["next_ts"] = 0.0
    await h.put_state(st)
    await h.tick()
    return h.tg.last_with_buttons()


async def test_an_early_practice_answer_grows_the_interval_by_three_quarters(h):
    """Two words in the same state, one answered as a practice card before it
    was due: its interval grows by EARLY_REVIEW_WEIGHT of the other's step."""
    from app.infrastructure.repositories.user_tracks import UserTrackRepository
    from app.infrastructure.repositories.users import UserRepository

    rows = await h.sql(
        "select uw.id from user_words uw join words w on w.id = uw.word_id"
        " where uw.user_id=:u and w.level = 'A1' and w.translation is not null order by uw.id limit 2", u=UID,
    )
    a, b = rows[0][0], rows[1][0]
    await h.sql(
        "update user_words set status='learning', interval_days=4, ease_score=2.5, repetitions_count=3,"
        " mistakes_count=0, consecutive_wrong=0, learning_score=0.4, production_count=0, mastery_score=0,"
        " next_review_at = now() + interval '3 days' where id in (:a, :b)", a=a, b=b,
    )
    async with h.sm() as session:
        svc = ps.PushService(session, h.redis, h.bot)
        user = await UserRepository(session).get(UID)
        ut = await UserTrackRepository(session).get(UID, ps._TRACK)
        await svc._apply_word_answer(user, ut, a, True, card_type=ps.CARD_RECOGNITION)
        await svc._apply_word_answer(user, ut, b, True, card_type=ps.CARD_RECOGNITION, early_weight=True)
        await session.commit()
    (ia,), (ib,) = [
        (await h.sql("select interval_days from user_words where id=:i", i=i))[0] for i in (a, b)
    ]
    assert ia > 4, "the normal answer did not grow the interval at all"
    assert 4 < ib < ia, "an early answer must count, but for less"
    assert ib == pytest.approx(4 + (ia - 4) * ps.EARLY_REVIEW_WEIGHT, rel=1e-6)


async def test_a_due_word_answered_in_practice_counts_in_full(h):
    from app.infrastructure.repositories.user_tracks import UserTrackRepository
    from app.infrastructure.repositories.users import UserRepository

    (a,), (b,) = await h.sql(
        "select uw.id from user_words uw join words w on w.id = uw.word_id"
        " where uw.user_id=:u and w.level = 'A1' and w.translation is not null order by uw.id limit 2", u=UID,
    )
    await h.sql(
        "update user_words set status='learning', interval_days=4, ease_score=2.5, repetitions_count=3,"
        " mistakes_count=0, learning_score=0.4, production_count=0, mastery_score=0,"
        " next_review_at = now() - interval '1 hour' where id in (:a, :b)", a=a, b=b,
    )
    async with h.sm() as session:
        svc = ps.PushService(session, h.redis, h.bot)
        user = await UserRepository(session).get(UID)
        ut = await UserTrackRepository(session).get(UID, ps._TRACK)
        await svc._apply_word_answer(user, ut, a, True, card_type=ps.CARD_RECOGNITION)
        await svc._apply_word_answer(user, ut, b, True, card_type=ps.CARD_RECOGNITION, early_weight=True)
        await session.commit()
    ia = (await h.sql("select interval_days from user_words where id=:i", i=a))[0][0]
    ib = (await h.sql("select interval_days from user_words where id=:i", i=b))[0][0]
    assert ib == pytest.approx(ia)


async def test_practice_picks_due_then_most_missed_then_longest_unseen(h):
    from app.infrastructure.repositories.user_words import UserWordRepository

    now = datetime.now(timezone.utc)
    await h.sql(
        "update user_words set status='learning', archived=false, snooze_until=null, mistakes_count=0,"
        " next_review_at = now() + interval '10 days', last_reviewed_at = now() where user_id=:u", u=UID,
    )
    ids = [r[0] for r in await h.sql("select id from user_words where user_id=:u order by id limit 3", u=UID)]
    due, missed, old = ids
    await h.sql("update user_words set next_review_at = now() - interval '1 day' where id=:i", i=due)
    await h.sql("update user_words set mistakes_count = 5 where id=:i", i=missed)
    await h.sql("update user_words set last_reviewed_at = now() - interval '90 days' where id=:i", i=old)
    async with h.sm() as session:
        repo = UserWordRepository(session)
        picks = []
        for _ in range(3):
            uw, _w = await repo.pick_practice(UID, ps._TRACK, exclude=picks, now=now)
            picks.append(uw.id)
    assert picks == [due, missed, old]


async def test_practice_never_offers_a_new_word(h):
    from app.infrastructure.repositories.user_words import UserWordRepository

    await h.sql("update user_words set status='new' where user_id=:u", u=UID)
    async with h.sm() as session:
        assert await UserWordRepository(session).pick_practice(UID, ps._TRACK, exclude=[]) is None


async def test_nothing_to_practise_ends_the_lesson_and_says_so(h, monkeypatch):
    _recognition(monkeypatch)
    await h.fresh_day(["new_word"])
    await h.say(BTN_LESSON)
    card = (await h.state())["inflight"]
    await h.tap_text(card["msg_id"], card["correct"])
    offer = h.tg.last_with_buttons()
    # Everything back to unstarted: there is nothing learned to practise.
    await h.sql("update user_words set status='new' where user_id=:u", u=UID)
    await h.act(offer["id"], "practice")
    st = await h.state()
    assert "lesson" not in st and "extra" not in st
    assert any(e["text"] == EXTRA_NOTHING_TO_PRACTISE for e in h.tg.sent)
    await h.check_invariants()


async def test_more_new_words_by_push(h, monkeypatch):
    from app.services.backlog_service import BacklogService

    _recognition(monkeypatch)

    async def room(self, user_id, track):
        return 10, 3

    monkeypatch.setattr(BacklogService, "room", room)
    await h.fresh_day(["new_word"])
    offer = await _close_plan_by_push(h)
    await h.act(offer["id"], "more")
    card = (await h.state())["inflight"]
    assert card and card.get("extra") == "new" and card.get("plan_kind") is None
    await h.tap_text(card["msg_id"], card["correct"])
    assert await h.plan() == []  # extra words never reopen a plan
    await h.check_invariants()


async def test_enough_by_push_goes_quiet(h, monkeypatch):
    _recognition(monkeypatch)
    await h.fresh_day(["new_word"])
    offer = await _close_plan_by_push(h)
    await h.act(offer["id"], "enough")
    st = await h.state()
    assert "extra" not in st and st["inflight"] is None
    st["next_ts"] = 0.0
    await h.put_state(st)
    assert await h.tick() is False
    await h.check_invariants()


async def test_topic_check_answers_count_toward_the_pace(h):
    from app.infrastructure.repositories.reviews import WordReviewRepository

    async def pace() -> float:
        async with h.sm() as session:
            return await WordReviewRepository(session).typical_daily_answers(UID, ps._TRACK, days=1) or 0.0

    # Start from a clean day: the restored copy carries the learner's real
    # answers from today.
    await h.sql("delete from word_reviews where user_id=:u", u=UID)
    await h.sql("delete from analytics_events where user_id=:u and name='phrase_answered'", u=UID)
    await h.sql(
        "update user_grammar_topics set passed_at = now() - interval '10 days',"
        " test_due_at = now() - interval '1 day' where user_id=:u and topic_id=1", u=UID,
    )
    await h.fresh_day(["test", "new_word"])
    card = await h.card()
    await h.act(card["msg_id"], "tstart")
    for pid in card["phrases"]:
        en = (await h.sql("select en from grammar_phrases where id=:i", i=pid))[0][0]
        await h.say(en)
    assert await pace() == len(card["phrases"])
