"""The batch triage screen: toggling, and what the labels have to show."""
from __future__ import annotations

from app.bot.keyboards.push import triage_kb
from app.domain.triage import BATCH_SIZE, TriageState, button_label, render

TELEGRAM_CALLBACK_LIMIT = 64
TELEGRAM_BUTTON_TEXT_LIMIT = 64


def test_toggling_is_reversible():
    """A mis-tap must be recoverable without restarting the screen."""
    state = TriageState().toggle(5)
    assert state.marked(5)
    assert not state.toggle(5).marked(5)


def test_marking_one_word_leaves_the_others_alone():
    state = TriageState().toggle(1).toggle(2).toggle(1)
    assert state.known == (2,)


def test_state_survives_a_round_trip():
    state = TriageState(known=(3, 9))
    assert TriageState.from_dict(state.to_dict()) == state
    assert TriageState.from_dict(None) == TriageState()


def test_the_label_shows_the_meaning_being_judged():
    """«charge» is a different question depending on whether it means «заряд»
    or «плата», and the learner cannot answer honestly without knowing which."""
    label = button_label("charge", "плата / заряд", marked=False)
    assert "charge" in label and "плата" in label


def test_a_marked_word_looks_marked():
    assert button_label("house", "дом", marked=True) != button_label("house", "дом", marked=False)


def test_a_long_gloss_cannot_break_the_button():
    label = button_label("word", "очень длинный перевод " * 10, marked=True)
    assert len(label) <= TELEGRAM_BUTTON_TEXT_LIMIT


def test_a_word_without_a_translation_still_renders():
    assert button_label("house", "", marked=False) == "house"


def test_every_callback_fits_the_budget():
    kb = triage_kb([(999_999_999, "x" * 60)] * BATCH_SIZE, "Готово")
    for row in kb.inline_keyboard:
        for b in row:
            assert len(b.callback_data.encode()) <= TELEGRAM_CALLBACK_LIMIT


def test_the_screen_always_offers_a_way_out():
    """Without «Готово» the only exit is ignoring the card, and an ignored
    card is the one thing the plan cannot tell apart from being busy."""
    kb = triage_kb([(1, "a")], "Готово")
    assert any("trgok" in b.callback_data for row in kb.inline_keyboard for b in row)


def test_the_text_says_how_far_along_the_learner_is():
    assert "3 из 15" in render("Дом", offered=15, known=3)


def test_the_theme_title_cannot_break_the_message():
    assert "<script>" not in render("<script>", offered=1, known=0)
