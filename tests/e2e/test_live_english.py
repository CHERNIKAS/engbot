"""«🗣 Живой английский»: opt-in, and once added its phrases are taught."""
from __future__ import annotations

from app.bot import texts as T
from app.services import push_service as ps
from tests.e2e.harness import UID


async def _live_owned(h) -> int:
    rows = await h.sql(
        "select count(*) from user_words uw join pack_words pw on pw.word_id = uw.word_id"
        " join packs p on p.id = pw.pack_id where uw.user_id=:u and p.category='Живой английский'", u=UID,
    )
    return rows[0][0]


async def test_the_collection_is_not_added_on_its_own(h):
    """Only «Темы» and «Фразы» are stocked automatically."""
    await h.fresh_day(["new_word", "phrase"])
    await h.card()
    assert await _live_owned(h) == 0


async def test_added_from_collections_its_phrases_come_through_the_phrase_slot(h, monkeypatch):
    monkeypatch.setattr(ps.PushService, "_card_type", lambda self, uw, word, user_level=None: ps.CARD_RECOGNITION)
    await h.fresh_day(["phrase", "phrase"])
    await h.say(T.BTN_COLLECTIONS)
    groups = h.tg.last_with_buttons()["id"]
    live = next(d for t, d in h.tg.buttons(groups) if "Живой английский" in t)
    await h.tap(groups, live)
    packs = h.tg.last_with_buttons()["id"]
    reactions = next(d for t, d in h.tg.buttons(packs) if "Реакции" in t)
    await h.tap(packs, reactions)
    assert await _live_owned(h) == 20
    # Everything else in the phrase stream done: the next phrase is a live one.
    await h.sql(
        "update user_words set status='mastered' where user_id=:u and word_id not in"
        " (select pw.word_id from pack_words pw join packs p on p.id = pw.pack_id"
        "  where p.category='Живой английский') and word_id in (select id from words where is_phrase)",
        u=UID,
    )
    card = await h.card()
    writing = (await h.sql("select w.writing from user_words uw join words w on w.id=uw.word_id where uw.id=:i",
                           i=card["id"]))[0][0]
    assert writing == "No way!"
    assert "You met Taylor Swift" in h.tg.live[card["msg_id"]]["text"]  # the usage example rides along
    await h.check_invariants()
