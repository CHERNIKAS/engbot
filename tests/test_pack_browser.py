from __future__ import annotations

from app.bot.keyboards.packs import pack_browser_kb
from app.domain.models import Pack


def test_pack_row_shows_count_and_learned_percent():
    p = Pack(id=1, title="Еда", words_count=200)
    kb = pack_browser_kb([p], {1: (50, 40)}, selected={1}, page=0, total_pages=1)
    btn = kb.inline_keyboard[0][0]
    assert "Еда" in btn.text
    assert "200" in btn.text
    assert "20%" in btn.text  # 40 mastered / 200 total
    assert btn.text.startswith("✅")  # selected


def test_pack_row_unselected_and_zero_safe():
    p = Pack(id=2, title="IT", words_count=0)
    kb = pack_browser_kb([p], {}, selected=set(), page=0, total_pages=1)
    btn = kb.inline_keyboard[0][0]
    assert btn.text.startswith("☑️")
    assert "0%" in btn.text  # no division-by-zero


def test_add_selected_button_only_when_selection_nonempty():
    p = Pack(id=1, title="Еда", words_count=10)
    flat_none = [b.text for row in pack_browser_kb([p], {}, set(), 0, 1).inline_keyboard for b in row]
    assert not any("Добавить выбранные" in t for t in flat_none)
    flat_sel = [b.text for row in pack_browser_kb([p], {}, {1}, 0, 1).inline_keyboard for b in row]
    assert any("Добавить выбранные (1)" in t for t in flat_sel)
