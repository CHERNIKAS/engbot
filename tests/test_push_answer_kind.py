"""Which credit a push answer earns, and how long an ignored card waits.

Mutation testing found _answer_kind effectively untested: flipping
`if not correct` -- grading every right answer as WRONG and every wrong one
as right -- passed the whole suite. The nudge backoff was just as loose:
`* 60` to `/ 60` survived, which would re-push an ignored card every ten
seconds instead of every ten minutes.
"""
from __future__ import annotations

from app.domain import mastery
from app.services.push_service import (
    CARD_CLOZE,
    CARD_RECOGNITION,
    CARD_REVERSE,
    CARD_TYPE_IN,
    _answer_kind,
    _retry_after,
)

ALL_CARDS = (CARD_RECOGNITION, CARD_REVERSE, CARD_CLOZE, CARD_TYPE_IN)


def test_a_right_answer_earns_the_credit_of_its_card():
    assert _answer_kind(CARD_RECOGNITION, True) == mastery.RECOGNITION
    assert _answer_kind(CARD_REVERSE, True) == mastery.REVERSE
    assert _answer_kind(CARD_CLOZE, True) == mastery.TYPED_EXACT
    assert _answer_kind(CARD_TYPE_IN, True) == mastery.TYPED_EXACT


def test_a_wrong_answer_is_wrong_on_every_card():
    for card in (*ALL_CARDS, None):
        assert _answer_kind(card, False) == mastery.WRONG


def test_an_unknown_card_is_credited_as_the_cheapest_kind():
    """Better to under-credit a card we cannot identify than to hand it the
    typed-answer credit it may not have earned."""
    assert _answer_kind(None, True) == mastery.RECOGNITION
    assert _answer_kind("mystery", True) == mastery.RECOGNITION


def test_an_ignored_card_waits_minutes_not_seconds():
    for _ in range(200):
        assert 8 * 60 <= _retry_after(0) <= 12 * 60
        assert 8 * 60 <= _retry_after(1) <= 12 * 60
        assert 16 * 60 <= _retry_after(2) <= 24 * 60
        assert 32 * 60 <= _retry_after(3) <= 48 * 60


def test_the_backoff_stops_growing_at_forty_minutes():
    for _ in range(200):
        assert _retry_after(9) <= 48 * 60
