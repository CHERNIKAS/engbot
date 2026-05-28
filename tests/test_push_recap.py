"""Post-answer recap block under a push card: word recap shows the
writing→translation and the example with the target word bolded; grammar recap
fills the prompt's "___" gap with the bolded correct form. Showing it only
AFTER the answer is the whole point (the example contains the target word, so
exposing it during the quiz would spoil)."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.push_service import (
    _grammar_recap,
    _highlight_target,
    _word_recap,
)


def test_highlight_target_bolds_first_match_case_insensitively():
    out = _highlight_target("The cat is sleeping.", "cat")
    assert out == "The <b>cat</b> is sleeping."


def test_highlight_target_is_case_insensitive():
    out = _highlight_target("Cats and a CAT.", "cat")
    # Only the first match is bolded (don't double-mark plurals etc.).
    assert out.startswith("<b>Cat</b>s")
    assert out.count("<b>") == 1


def test_highlight_target_html_escapes_then_bolds():
    """If the sentence has < or &, those are escaped BEFORE we inject bold."""
    out = _highlight_target("a & b cat", "cat")
    assert "&amp;" in out
    assert "<b>cat</b>" in out


def test_highlight_target_target_not_found_returns_plain():
    out = _highlight_target("She went home.", "go")
    # "go" inside "went" is NOT a clean lexical match; we just skip bolding.
    # The pure-regex impl WILL match "go" only if it's literal in the sentence;
    # otherwise the sentence is returned escaped, no markup.
    assert "<b>" not in out
    assert out == "She went home."


def test_word_recap_with_example():
    word = SimpleNamespace(writing="cat", example_sentence="The cat is sleeping.")
    out = _word_recap(word, correct_translation="кот")
    assert out.startswith("\n\n<b>cat</b> — кот\n")
    assert "📝 <i>The <b>cat</b> is sleeping.</i>" in out


def test_word_recap_without_example():
    word = SimpleNamespace(writing="haven't", example_sentence=None)
    out = _word_recap(word, correct_translation="не имею")
    assert out == "\n\n<b>haven&#x27;t</b> — не имею"


def test_word_recap_escapes_html_in_writing_and_translation():
    word = SimpleNamespace(writing="A&B", example_sentence=None)
    out = _word_recap(word, correct_translation="<x>")
    assert "&amp;" in out
    assert "&lt;x&gt;" in out


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
    # The bold tags themselves are not escaped — they're our markup.
    assert "<b>&lt;x&gt;</b>" in out
