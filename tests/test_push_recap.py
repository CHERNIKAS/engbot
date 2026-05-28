"""Word push cards now carry the example sentence ON the card itself, with the
target word (and its basic inflections) masked with ___ so it works as a
context CLUE without spoiling the answer. The post-answer feedback is just a
small `writing — translation` line — the example was already shown.

Grammar cards carry the gap-prompt as before, with a filled-in reveal in the
feedback.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.push_service import (
    _grammar_recap,
    _mask_target,
    _word_recap,
)


# ---- _mask_target --------------------------------------------------------

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


# ---- _word_recap ---------------------------------------------------------

def test_word_recap_is_just_writing_and_translation():
    """The example lives on the quiz card now — feedback only confirms the
    word + meaning, no duplication of the sentence."""
    word = SimpleNamespace(writing="cat", example_sentence="The cat is sleeping.")
    out = _word_recap(word, correct_translation="кот")
    assert out == "\n\n<b>cat</b> — кот"
    assert "📝" not in out
    assert "sleeping" not in out


def test_word_recap_escapes_html_in_writing_and_translation():
    word = SimpleNamespace(writing="A&B", example_sentence=None)
    out = _word_recap(word, correct_translation="<x>")
    assert "&amp;" in out
    assert "&lt;x&gt;" in out


# ---- _grammar_recap (unchanged) ------------------------------------------

def test_grammar_recap_fills_gap_with_bold():
    out = _grammar_recap("She ___ to school.", "goes")
    assert out == "\n\n📝 <i>She <b>goes</b> to school.</i>"


def test_grammar_recap_handles_multi_word_answer():
    out = _grammar_recap("Look! She ___ now.", "is running")
    assert "<b>is running</b>" in out
    assert "Look! She <b>is running</b> now." in out


def test_grammar_recap_escapes_html():
    out = _grammar_recap("Use ___ here.", "<x>")
    assert "&lt;x&gt;" in out
    assert "<b>&lt;x&gt;</b>" in out
