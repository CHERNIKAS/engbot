from __future__ import annotations

from app.bot.keyboards.packs import pack_browser_kb


def test_added_pack_shows_green_check():
    # rows: (pack_id, title, words_count, learned_pct, owned)
    kb = pack_browser_kb([(1, "Еда", 28, 20, 28)], page=0, total_pages=1)
    btn = kb.inline_keyboard[0][0]
    assert "Еда" in btn.text and "28" in btn.text and "20%" in btn.text
    assert btn.text.startswith("✅")  # fully owned → added


def test_not_added_pack_shows_empty_box():
    kb = pack_browser_kb([(2, "Дом", 20, 0, 0)], page=0, total_pages=1)
    assert kb.inline_keyboard[0][0].text.startswith("⬜")


def test_partial_owned_counts_as_not_added():
    kb = pack_browser_kb([(3, "Город", 20, 0, 5)], page=0, total_pages=1)
    assert kb.inline_keyboard[0][0].text.startswith("⬜")


def test_zero_words_safe():
    kb = pack_browser_kb([(4, "Пусто", 0, 0, 0)], page=0, total_pages=1)
    assert kb.inline_keyboard[0][0].text.startswith("⬜")


def test_course_managed_rows_are_info_only():
    kb = pack_browser_kb([(9, "A1", 262, 0, 5)], page=0, total_pages=1, course_managed=True)
    btn = kb.inline_keyboard[0][0]
    assert btn.text.startswith("🎓")
    assert "course_info" in btn.callback_data


def test_no_batch_add_button():
    flat = [b.text for row in pack_browser_kb([(1, "Еда", 10, 0, 0)], 0, 1).inline_keyboard for b in row]
    assert not any("Добавить выбранные" in t for t in flat)
    assert any("Группы" in t for t in flat)
