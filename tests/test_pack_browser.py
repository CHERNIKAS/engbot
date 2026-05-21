from __future__ import annotations

from app.bot.keyboards.packs import pack_browser_kb


def test_pack_row_shows_count_and_learned_percent():
    kb = pack_browser_kb([(1, "Еда", 200, 20)], selected={1}, page=0, total_pages=1)
    btn = kb.inline_keyboard[0][0]
    assert "Еда" in btn.text
    assert "200" in btn.text
    assert "20%" in btn.text
    assert btn.text.startswith("✅")  # selected


def test_pack_row_unselected_and_zero_safe():
    kb = pack_browser_kb([(2, "IT", 0, 0)], selected=set(), page=0, total_pages=1)
    btn = kb.inline_keyboard[0][0]
    assert btn.text.startswith("☑️")
    assert "0%" in btn.text


def test_add_selected_button_only_when_selection_nonempty():
    flat_none = [b.text for row in pack_browser_kb([(1, "Еда", 10, 0)], set(), 0, 1).inline_keyboard for b in row]
    assert not any("Добавить выбранные" in t for t in flat_none)
    flat_sel = [b.text for row in pack_browser_kb([(1, "Еда", 10, 0)], {1}, 0, 1).inline_keyboard for b in row]
    assert any("Добавить выбранные (1)" in t for t in flat_sel)
