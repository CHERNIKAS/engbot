"""Word push cards carry the example sentence ON the card itself, with the
target word (and its basic inflections) masked with ___ so it works as a
context CLUE without spoiling the answer.

After the answer the card is replaced with just «✅ Верно! 🎉» / «❌ Мимо.
Правильно: X» — no extra recap, the user already had the example on the card.
"""
from __future__ import annotations

from app.services.push_service import _mask_target


def test_mask_target_replaces_basic_inflection():
    assert _mask_target("She teaches English at a local school.", "teach") == (
        "She ___ English at a local school."
    )


def test_mask_target_replaces_past_regular():
    assert _mask_target("Profits soared after the launch.", "soar") == (
        "Profits ___ after the launch."
    )


def test_mask_target_replaces_ing():
    assert _mask_target("She is teaching now.", "teach") == "She is ___ now."


def test_mask_target_handles_apostrophe_in_target():
    assert _mask_target("I haven't seen him today.", "haven't") == (
        "I ___ seen him today."
    )


def test_mask_target_case_insensitive_masks_all_occurrences():
    out = _mask_target("Cats and a CAT.", "cat")
    assert out == "___ and a ___."


def test_mask_target_returns_none_on_irregular_form():
    """We can't mask 'went' from 'go' — better to show no example than leak
    by showing the answer."""
    assert _mask_target("She went home yesterday.", "go") is None


def test_mask_target_returns_none_when_target_absent():
    assert _mask_target("Hello world.", "cat") is None


def test_mask_target_empty_inputs():
    assert _mask_target("", "teach") is None
    assert _mask_target("She teaches.", "") is None


def test_mask_target_word_boundary_no_false_positive():
    """'cat' must NOT match inside 'category'."""
    assert _mask_target("The category is open.", "cat") is None
