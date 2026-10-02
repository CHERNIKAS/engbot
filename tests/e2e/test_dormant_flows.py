"""Flows the crawler cannot reach from a default bot, driven on purpose.

Each sits behind a condition the restored copy does not meet — a feature flag,
a drill stage, an oversized pool — and so went untested. Arranged here instead
of being excused from the coverage check.
"""
from __future__ import annotations

from app.bot import texts as T
from tests.e2e.harness import UID


def _kind(data: str) -> str:
    return ":".join(data.split(":")[:2])


async def _press(h, prefix: str, nth: int = 0, mid: int | None = None) -> None:
    """Tap the nth button whose data starts with `prefix` (e.g. "st:start")."""
    mid = mid or h.tg.last_with_buttons()["id"]
    found = [d for _t, d in h.tg.buttons(mid) if d.startswith(prefix)]
    assert len(found) > nth, f"no {prefix!r} on screen: {h.tg.buttons(mid)}"
    await h.tap(mid, found[nth])


async def test_study_reaches_the_typing_stage(h):
    """«Учить» drills a word as a quiz, then typed: a correct quiz answer
    queues the typing card, with its hint and skip."""
    await h.fresh_day(["new_word"])
    await h.say(T.BTN_STUDY)
    await _press(h, "st:start")
    typed = False
    for _ in range(40):
        card = h.tg.last_with_buttons()
        acts = {_kind(d) for _t, d in h.tg.buttons(card["id"])}
        if "st:hint" in acts:
            await _press(h, "st:hint", mid=card["id"])
            await _press(h, "st:skip", mid=card["id"])
            await h.say("definitely-not-the-word")
            typed = True
            break
        if "st:answer" not in acts:
            break
        # The quiz shows the word in bold; the right option is its gloss.
        word = card["text"].split("<b>")[-1].split("</b>")[0]
        rows = await h.sql(
            "select coalesce(w.translation, '') from words w join user_words uw on uw.word_id = w.id"
            " where uw.user_id = :u and w.writing = :w limit 1", u=UID, w=word,
        )
        gloss = rows[0][0] if rows else ""
        labels = [(t, d) for t, d in h.tg.buttons(card["id"]) if _kind(d) == "st:answer"]
        pick = next((d for t, d in labels if t and gloss and (t in gloss or gloss.startswith(t))), labels[0][1])
        await h.tap(card["id"], pick)
    assert typed, "never reached a typing card"
    await h.check_invariants()


async def test_the_track_picker_when_japanese_is_on(h):
    from app.config import get_settings

    settings = get_settings()
    before = settings.enable_japanese, settings.access_password
    object.__setattr__(settings, "enable_japanese", True)
    object.__setattr__(settings, "access_password", "")
    try:
        h.tg_id = 990_000_101
        await h.say("/start")
        intro = h.tg.last_with_buttons()["id"]
        await _press(h, "ob:start", mid=intro)
        picker = h.tg.last_with_buttons()["id"]
        await _press(h, "ob:toggle_track", 1, mid=picker)
        await _press(h, "ob:toggle_track", 1, mid=picker)
        await _press(h, "ob:tracks_done", mid=picker)
    finally:
        object.__setattr__(settings, "enable_japanese", before[0])
        object.__setattr__(settings, "access_password", before[1])
        h.tg_id = h.__class__.tg_id
    await h.check_invariants()


async def test_an_oversized_pool_is_offered_a_rest(h):
    await h.fresh_day(["new_word"])
    # Everything in the active pool at once: far past any pace's ceiling.
    await h.sql("update user_words set status='learning', archived=false, snooze_until=null where user_id=:u", u=UID)
    await h.say(T.BTN_PROGRESS)
    await _press(h, "pg:backlog")
    await _press(h, "pg:park")
    await h.check_invariants()
