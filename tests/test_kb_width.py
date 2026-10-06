"""No push keyboard puts more than two buttons in a row.

Inline buttons take the width of their message; under a short sentence three
across were cut to «…зка», «…ило», «…мню» (2026-10-06). Answer options already
go two to a row; this pins the control rows too.
"""
from __future__ import annotations

from app.bot.keyboards.push import constructor_slots_kb, constructor_typing_kb


def _widest(kb) -> int:
    return max(len(row) for row in kb.inline_keyboard)


def test_typing_card_rows_hold_two_at_most():
    assert _widest(constructor_typing_kb(1)) <= 2


def test_assisted_card_rows_hold_two_at_most_with_undo():
    assert _widest(constructor_slots_kb(["a", "b", "c", "d"], 1, can_undo=True)) <= 2
    assert _widest(constructor_slots_kb(["a", "b", "c"], 1, can_undo=False)) <= 2
