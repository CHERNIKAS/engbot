"""Typing-mode hints, step by step (2026-10-06: «а подсказку дает всего одну?»)."""
from __future__ import annotations

from dataclasses import replace

from app.domain import constructor as c

EN = "I often work at home."


def test_each_hint_shows_one_more_word_and_never_the_last():
    st = c.CardState(typing=True)
    shown = []
    while (n := c.next_hint_words(st, EN)) is not None:
        st = replace(c.use_hint(st), hint_words=n)
        shown.append(c.hint_prefix(EN, reveal=n))
    assert shown == ["I often", "I often work", "I often work at"]


def test_each_extra_word_costs_a_little_more():
    first = c.credit(1, hinted=True, hint_words=2)
    second = c.credit(1, hinted=True, hint_words=3)
    third = c.credit(1, hinted=True, hint_words=4)
    assert c.credit(1) > first > second > third >= c.MIN_CREDIT
    assert first == c.credit(1, hinted=True)  # the first hint costs what it did


def test_a_card_hinted_before_this_change_continues_from_two_words():
    old = c.CardState.from_dict({"typing": True, "hinted": True})
    assert c.next_hint_words(old, EN) == 3


def test_hint_words_survive_redis():
    st = c.CardState(typing=True, hinted=True, hint_words=3)
    assert c.CardState.from_dict(st.to_dict()).hint_words == 3
