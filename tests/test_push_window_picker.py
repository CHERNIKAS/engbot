"""The push-window picker.

Both grids used to be on screen at once, and every hour appears in each of
them — so "21" under «Начало» is indistinguishable from "21" under «Конец».
Users picked a start hour and then an end hour in the same grid and watched
the first choice get replaced: "выбирает или то или другое". One grid at a
time is the fix, and these pin it.
"""
from __future__ import annotations

from app.bot.keyboards.settings import push_window_kb

MIN_HOURS = 5


def _labels(kb) -> list[str]:
    return [b.text for row in kb.inline_keyboard for b in row]


def _cell(kb, hour: str) -> str | None:
    for row in kb.inline_keyboard:
        for b in row:
            if b.text.strip("·") == hour:
                return b.callback_data
    return None


def _value(cb: str) -> str:
    return cb.split(":")[2]


# ---- one grid at a time ----


def test_only_one_hour_grid_is_ever_on_screen():
    """The whole bug in one assertion: an hour must mean exactly one thing."""
    for step in ("ws", "we"):
        kb = push_window_kb(16, 2, MIN_HOURS, step=step)
        for hour in ("14", "21"):
            hits = [
                b for row in kb.inline_keyboard for b in row if b.text.strip("·") == hour
            ]
            assert len(hits) == 1, f"{hour} appears {len(hits)} times on step {step}"


def test_the_start_step_shows_the_start_question_only():
    kb = push_window_kb(16, 2, MIN_HOURS, step="ws")
    assert "🌅 Во сколько начинать?" in _labels(kb)
    assert "🌙 До скольки?" not in _labels(kb)


def test_the_end_step_shows_the_end_question_only():
    kb = push_window_kb(16, 2, MIN_HOURS, step="we")
    assert "🌙 До скольки?" in _labels(kb)
    assert "🌅 Во сколько начинать?" not in _labels(kb)


def test_the_keyboard_stays_short_enough_to_fit_on_a_phone():
    """The old two-grid layout pushed the end grid's last row (19-24) below the
    fold, behind the message box — the hours most likely wanted for an end were
    the hardest to reach."""
    for step in ("ws", "we"):
        assert len(push_window_kb(16, 2, MIN_HOURS, step=step).inline_keyboard) <= 9


# ---- the three taps that set 14:00-21:00 ----


def test_picking_a_start_hour_sets_the_start_and_moves_on():
    kb = push_window_kb(16, 2, MIN_HOURS, step="ws")
    assert _value(_cell(kb, "14")) == "w_14_2"  # op "w" → advance to the end grid


def test_picking_an_end_hour_sets_the_end_and_stays_put():
    kb = push_window_kb(14, 2, MIN_HOURS, step="we")
    assert _value(_cell(kb, "21")) == "e_14_21"  # op "e" → stay on the end grid


def test_the_save_button_carries_the_pair_the_user_actually_built():
    kb = push_window_kb(14, 21, MIN_HOURS, step="we")
    save = next(b for row in kb.inline_keyboard for b in row if b.text == "✅ Сохранить")
    assert _value(save.callback_data) == "sv_14_21"


def test_the_chosen_hour_is_marked_on_each_step():
    assert "·14·" in _labels(push_window_kb(14, 21, MIN_HOURS, step="ws"))
    assert "·21·" in _labels(push_window_kb(14, 21, MIN_HOURS, step="we"))


def test_the_start_can_be_changed_without_starting_over():
    kb = push_window_kb(14, 21, MIN_HOURS, step="we")
    back = next(b for row in kb.inline_keyboard for b in row if b.text.startswith("⬅️"))
    assert _value(back.callback_data) == "b_14_21"  # op "b" → back to the start grid
    assert "14:00" in back.text  # says what it is going back to


# ---- what the end step tells you ----


def test_the_end_step_names_the_window_it_would_save():
    kb = push_window_kb(14, 21, MIN_HOURS, step="we")
    assert any("14:00 → 21:00 · 7 ч" in b.text for row in kb.inline_keyboard for b in row)


def test_an_overnight_window_is_called_out():
    kb = push_window_kb(22, 8, MIN_HOURS, step="we")
    assert any("через ночь" in b.text for row in kb.inline_keyboard for b in row)


def test_a_window_under_the_minimum_is_flagged_before_saving():
    kb = push_window_kb(22, 2, MIN_HOURS, step="we")
    assert any(b.text.startswith("⚠️") and "≥ 5 ч" in b.text for row in kb.inline_keyboard for b in row)


def test_the_start_step_does_not_nag_about_length():
    """Mid-pick the pair is half-chosen; warning about it is noise."""
    kb = push_window_kb(22, 2, MIN_HOURS, step="ws")
    assert not any(b.text.startswith("⚠️") for row in kb.inline_keyboard for b in row)
