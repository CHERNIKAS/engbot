"""Word push cards now carry an *abstract* example: a paraphrased English
sentence (using a synonym so the target word doesn't appear) plus its Russian
translation. Both fields must be present — when either is missing the card
shows no example at all. After-answer feedback stays minimal: just ✅/❌.
"""
from __future__ import annotations

from app.services.push_service import _format_word_card


def test_format_word_card_with_abstract_pair():
    out = _format_word_card(
        writing="haven't",
        abstract_en="She still hasn't called me back.",
        abstract_ru="Она мне до сих пор не перезвонила.",
        progress="🌱 1 / 10",
    )
    assert "haven&#x27;t" in out
    assert "📝 <i>She still hasn&#x27;t called me back.</i>" in out
    assert "↳ Она мне до сих пор не перезвонила." in out
    assert "🌱 1 / 10" in out


def test_format_word_card_no_abstract_skips_example_line():
    """No abstract authored yet → render the question + progress, no 📝 line."""
    out = _format_word_card(writing="cat", abstract_en=None, abstract_ru=None, progress="🌱 0 / 10")
    assert "cat" in out
    assert "📝" not in out
    assert "↳" not in out


def test_format_word_card_only_one_side_present_skips():
    """Half a pair is worse than nothing — skip until both sides are authored."""
    out = _format_word_card(writing="cat", abstract_en="A small pet", abstract_ru=None, progress="🌱 0 / 10")
    assert "📝" not in out
    out = _format_word_card(writing="cat", abstract_en=None, abstract_ru="Маленький питомец", progress="🌱 0 / 10")
    assert "📝" not in out


def test_format_word_card_escapes_html_in_examples():
    out = _format_word_card(
        writing="A&B",
        abstract_en="Use <x> here",
        abstract_ru="Используй <y> тут",
        progress="🌱 0 / 10",
    )
    assert "A&amp;B" in out
    assert "&lt;x&gt;" in out
    assert "&lt;y&gt;" in out
