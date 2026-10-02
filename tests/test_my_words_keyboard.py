"""What «Мой словарь» offers, pinned where it stopped matching the product.

Folders predate v2. Words now arrive through `_top_up` with no category, so the
folders stopped filling — 59 of 65 empty — and the screen became two scrolls of
«(0)» around one real row.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.bot.keyboards.my_words import categories_overview_kb


def _labels(kb):
    return [b.text for row in kb.inline_keyboard for b in row]


def _cat(cid, name):
    return SimpleNamespace(id=cid, name=name)


def test_empty_folders_are_not_listed():
    kb = categories_overview_kb(
        [_cat(1, "Еда"), _cat(2, "Цвета"), _cat(3, "Числа")],
        {None: 91, 1: 0, 2: 0, 3: 8},
    )
    labels = _labels(kb)
    assert any("Числа" in t for t in labels)
    assert not any("Еда" in t for t in labels)
    assert not any("Цвета" in t for t in labels)


def test_the_real_rows_survive():
    """Everything holding words is still there — this hides nothing useful."""
    kb = categories_overview_kb([_cat(1, "Еда")], {None: 91, 1: 8})
    labels = _labels(kb)
    assert any("Все слова (99)" in t for t in labels)
    assert any("Без категории (91)" in t for t in labels)
    assert any("Еда (8)" in t for t in labels)


def test_collections_are_reachable_from_here():
    """They left the bottom menu; the narrow packs someone picks deliberately
    still need a way in, and this is the screen about your vocabulary."""
    kb = categories_overview_kb([], {None: 5})
    assert any("Коллекции" in t for t in _labels(kb))
