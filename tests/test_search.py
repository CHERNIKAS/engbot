"""Search: LIKE-pattern escaping and results keyboard layout."""
from __future__ import annotations

from app.bot.keyboards.search import search_results_kb
from app.infrastructure.repositories.words import like_pattern


def test_like_pattern_wraps_and_escapes():
    assert like_pattern("cat") == "%cat%"
    assert like_pattern("100%") == "%100\\%%"
    assert like_pattern("a_b") == "%a\\_b%"
    assert like_pattern("a\\b") == "%a\\\\b%"


def test_results_kb_sections_and_prefixes():
    kb = search_results_kb(
        own=[(7, "forget", "забывать")],
        catalog=[(42, "forgive", "прощать")],
    )
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert texts[0].startswith("📗 forget")
    assert texts[1].startswith("➕ forgive")
    assert texts[-1] == "🏠 В меню"
    own_btn = kb.inline_keyboard[0][0]
    add_btn = kb.inline_keyboard[1][0]
    assert own_btn.callback_data.startswith("mw:word")
    assert add_btn.callback_data.startswith("sr:add")
    assert ":42" in add_btn.callback_data


def test_results_kb_truncates_long_labels():
    kb = search_results_kb(
        own=[(1, "responsibility", "ответственность и ещё длинный хвост перевода")],
        catalog=[],
    )
    label = kb.inline_keyboard[0][0].text
    assert len(label) <= 40
    assert label.endswith("…")
