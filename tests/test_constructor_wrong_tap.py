"""A wrong tap in the assisted constructor must visibly do something.

2026-10-02, 21:48: the learner tapped an option on the last slot twice and «the
bot didn't care». Both taps were recorded as wrong (attempt 3 of 3) — but the
assisted card did not show attempts, so the re-render was identical, Telegram
refused the no-op edit, the refusal was swallowed, and the toast was empty.
"""
from __future__ import annotations

from app.domain import constructor as c


def _card(attempt: int) -> str:
    return c.render_card(topic_title="Present Simple", score=None, ru="Она не учится.",
                         built="She doesn't study", attempt=attempt)


def test_each_wrong_tap_changes_the_card():
    first, second, third = _card(1), _card(2), _card(3)
    assert len({first, second, third}) == 3
    assert "Попытка 2 из 3" in second


def test_a_first_attempt_card_is_not_cluttered():
    assert "Попытка" not in _card(1)
