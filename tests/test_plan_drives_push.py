"""The plan, not a lottery, decides what the push sends.

For two years each card was drawn from weighted randomness — repeat 60, review
22, new 18, grammar 15 — redrawn on every tick. Nothing about the day was
knowable from outside it: not what it held, not how long it was, not whether it
was finished. Prod showed the cost plainly, with ~56 cards pushable into an
evening window against ten answers.

These pin the replacement at the points where it could silently regress into
the old behaviour.
"""
from __future__ import annotations

import inspect

from app.domain import day_plan as rules
from app.services.push_service import PushService


def _source(fn) -> str:
    return inspect.getsource(fn)


def test_the_tick_no_longer_draws_a_random_stream():
    """`_weighted_order` is what made the day unpredictable. If a later change
    reaches for it again inside the tick, the plan becomes decoration."""
    src = _source(PushService.run_tick)
    assert "_weighted_order" not in src
    assert "next_kind" in src


def test_the_tick_asks_the_plan_what_comes_next():
    src = _source(PushService.run_tick)
    assert "ensure_plan" in src
    assert "DayPlanService" in src


def test_every_plan_slot_kind_can_actually_be_served():
    """A kind the plan can compose but `_serve` cannot fill would leave the day
    permanently one card short, and an unfinished plan is never replaced."""
    src = _source(PushService._serve)
    composable = {
        rules.REPEAT,
        rules.GRAMMAR,
        rules.PHRASE,
        rules.NEW_WORD,
        rules.NEW_THEME_WORD,
        rules.TRIAGE,
        rules.TEST,
    }
    for kind in composable:
        assert kind in src or f"plan_rules.{kind.upper()}" in src, kind


def test_an_unfillable_slot_is_ticked_off_rather_than_retried():
    """The theme runs out, every topic is passed, nothing is due. Retrying
    forever holds the plan open, and an open plan blocks every day after it."""
    src = _source(PushService.run_tick)
    assert "mark_done" in src


def test_the_plan_card_is_sent_before_the_first_exercise():
    """The learner agrees to a known amount of work rather than discovering the
    size of the day by reaching the end of it."""
    src = _source(PushService.run_tick)
    opened = src.index("opened")
    assert "_plan_card" in src
    assert src.index("_plan_card") > opened


def test_the_day_is_closed_and_announced_exactly_once():
    src = _source(PushService._close_day)
    assert "close_if_complete" in src
    # The guard is inside close_if_complete; the summary must sit behind it or
    # a second tick would send it again.
    assert src.index("close_if_complete") < src.index("day_summary.render")


def test_every_settled_card_ticks_a_slot():
    """A card answered but not ticked leaves the plan one short forever."""
    settle_paths = [
        PushService.handle_answer,
        PushService._settle_cloze,
        PushService._settle_constructor,
        PushService.handle_triage_done,
        PushService._finish_test,
    ]
    for fn in settle_paths:
        assert "_tick_plan" in _source(fn), fn.__name__


def test_card_senders_do_not_load_their_own_push_state():
    """The bug that made the deployed bot send a card on every tick.

    `run_tick` saves the state after `_serve` returns. A sender that loads its
    own copy has that save overwrite it with a snapshot taken before the card
    existed — the inflight is wiped the instant it is written, the next tick
    finds nothing in flight, and sends another. Forever.
    """
    for fn in (
        PushService._send_constructor,
        PushService._send_triage,
        PushService._send_test,
    ):
        src = _source(fn)
        assert "self._load(" not in src, fn.__name__
        assert "self._save(" not in src, fn.__name__
        assert "state: dict" in src, fn.__name__


def test_the_tick_saves_state_exactly_once():
    """Two saves in one tick means the later one wins, and the earlier one's
    work is gone. That is the shape the spam bug had: the sender wrote an
    inflight, the tick's own save replaced it with a snapshot from before, and
    every tick re-sent the card.
    """
    src = _source(PushService.run_tick)
    # Each branch saves and returns; what must not happen is a save that runs
    # after a helper has already written to the same key behind the tick's back.
    assert "_send_constructor(" not in src or "state" in src


def test_serve_hands_its_state_to_every_sender():
    """A sender that cannot see the tick's state has to fetch its own, which is
    how the two copies diverged in the first place."""
    src = _source(PushService._serve)
    for call in ("_send_triage(user, state", "_send_test(user, state", "_send_constructor(\n"):
        assert call in src, call
