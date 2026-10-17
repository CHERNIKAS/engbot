"""The constructor card as the learner sees it, and the buttons under it.

Two failure modes are invisible until they happen in production: a callback
that overruns Telegram's 64-byte limit (the button silently does nothing), and
an unescaped angle bracket in generated content (Telegram rejects the whole
message and the card never arrives). Both are cheap to pin here.
"""
from __future__ import annotations

from app.bot.keyboards.push import constructor_slots_kb, constructor_typing_kb
from app.domain.constructor import (
    LAST_TYPED_MAX,
    MAX_ATTEMPTS,
    CardState,
    mark_mistakes,
    matches,
    miss,
    render_card,
    render_result,
)

TELEGRAM_CALLBACK_LIMIT = 64


def _callbacks(kb):
    return [b.callback_data for row in kb.inline_keyboard for b in row]


def test_every_callback_fits_telegram_budget():
    """Over the limit the button does nothing at all, with no error anywhere."""
    kb = constructor_slots_kb(["a" * 80, "b" * 80, "c", "d"], phrase_id=999_999_999, can_undo=True)
    for data in _callbacks(kb) + _callbacks(constructor_typing_kb(999_999_999)):
        assert len(data.encode()) <= TELEGRAM_CALLBACK_LIMIT, data


def test_options_are_addressed_by_index_not_text():
    """Encoding the option text would blow the budget on a long slot and break
    on aiogram's `:` separator the moment a slot contains one."""
    kb = constructor_slots_kb(["She", "They"], phrase_id=7, can_undo=False)
    assert "pu:slot:7:0:0" in _callbacks(kb)
    assert "pu:slot:7:1:0" in _callbacks(kb)


def test_undo_is_absent_until_there_is_something_to_undo():
    """A button that does nothing teaches the learner to distrust the ones
    beside it."""
    fresh = _callbacks(constructor_slots_kb(["a", "b"], 1, can_undo=False))
    started = _callbacks(constructor_slots_kb(["a", "b"], 1, can_undo=True))
    assert not any("pundo" in c for c in fresh)
    assert any("pundo" in c for c in started)


def test_typing_mode_offers_no_answers():
    """The absence of options is the whole point of the mode."""
    data = _callbacks(constructor_typing_kb(1))
    assert not any("slot" in c for c in data)
    assert any("pgiveup" in c for c in data)


def test_a_slot_with_an_odd_number_of_options_still_renders():
    kb = constructor_slots_kb(["a", "b", "c"], 1, can_undo=False)
    # three options, plus the hint and the rule
    assert len([b for row in kb.inline_keyboard for b in row]) == 3 + 2


def test_the_rule_is_reachable_from_the_card_in_both_modes():
    """The rule used to be a one-off card shown when the topic opened; it
    scrolled away and the mechanism never showed it again, so a learner building
    sentences had the grammar nowhere in sight."""
    for kb in (constructor_slots_kb(["a", "b"], 1, can_undo=False), constructor_typing_kb(1)):
        assert any("prule" in c for c in _callbacks(kb))


def test_generated_content_cannot_break_the_message():
    """Prompts and answers come from generation; one raw `<` makes Telegram
    reject the message, which reads as the card failing to arrive."""
    text = render_card(
        topic_title="A <b>topic</b>",
        score=0.8,
        ru="Он сказал <script>.",
        built="He said <x> & co",
    )
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&amp;" in text


def test_the_card_shows_what_has_been_built_so_far():
    """Echoing the partial sentence is why tapping through slots is not just a
    slower multiple choice."""
    text = render_card(topic_title="T", score=None, ru="Она не живет здесь.", built="She doesn't")
    assert "She doesn&#x27;t" in text
    assert "Она не живет здесь." in text


def test_the_card_holds_its_shape_before_the_first_tap():
    """Without a placeholder the card grows by a line on the first choice and
    the buttons jump under the thumb."""
    empty = render_card(topic_title="T", score=None, ru="Фраза.")
    built = render_card(topic_title="T", score=None, ru="Фраза.", built="She")
    assert len(empty.splitlines()) == len(built.splitlines())


def test_typing_mode_says_what_is_expected_and_how_much_is_left():
    text = render_card(
        topic_title="T", score=0.9, ru="Фраза.", typing=True, attempt=2, hinted_prefix="She d"
    )
    assert "Напиши по-английски" in text
    assert f"из {MAX_ATTEMPTS}" in text
    assert "She d" in text


def test_the_first_attempt_is_not_announced():
    """"Попытка 1 из 3" on an untouched card reads as a warning."""
    text = render_card(topic_title="T", score=None, ru="Фраза.", typing=True, attempt=1)
    assert "Попытка" not in text


def test_the_result_always_shows_the_full_sentence():
    """Even when correct: it may have taken three attempts, and seeing the
    whole sentence is the part that sticks."""
    text = render_result(ru="Фраза.", en="She doesn't live here.", correct=True, answer_credit=1.0)
    assert "She doesn&#x27;t live here." in text
    assert text.startswith("✅")


def test_a_partial_credit_is_stated_rather_than_hidden():
    text = render_result(ru="Ф.", en="X.", correct=True, answer_credit=0.6)
    assert "0.6" in text


def test_full_credit_is_not_explained():
    """Nothing happened worth a line."""
    text = render_result(ru="Ф.", en="X.", correct=True, answer_credit=1.0)
    assert "Засчитано" not in text


def test_a_miss_shows_the_checkers_explanation():
    text = render_result(
        ru="Ф.", en="She doesn't live here.", correct=False, answer_credit=0.0,
        hint="после doesn't нужна начальная форма",
    )
    assert text.startswith("❌")
    assert "начальная форма" in text


# ---- a typed miss, shown back (2026-10-17) -------------------------------- #
#
# The learner's message is deleted, and the card said only «Попытка 2 из 3»:
# a one-letter slip had to be found by retyping the whole sentence.


def _copies(kb):
    return [b.copy_text.text for row in kb.inline_keyboard for b in row if b.copy_text]


def test_the_wrong_word_is_marked_and_the_rest_is_not():
    marked = mark_mistakes("she doesn'n like cold coffee", "She does not like cold coffee.",
                           ["She doesn't like cold coffee."])
    assert marked == "she <u><b>doesn&#x27;n</b></u> like cold coffee"


def test_marking_is_against_the_nearest_accepted_rendering():
    """«doesn't» is right; against «does not» it would be marked as well."""
    marked = mark_mistakes("She doesn't likes cold coffee", "She does not like cold coffee.",
                           ["She doesn't like cold coffee."])
    assert "<u><b>likes</b></u>" in marked
    assert "<u><b>doesn&#x27;t</b></u>" not in marked


def test_a_missing_word_shows_where_it_goes():
    marked = mark_mistakes("She like coffee", "She doesn't like coffee.")
    assert marked == "She <u>…</u> like coffee"
    assert mark_mistakes("She doesn't like", "She doesn't like coffee.").endswith("<u>…</u>")


def test_marking_ignores_case_and_punctuation():
    assert "<u>" not in mark_mistakes("she doesn’t like cold coffee", "She doesn't like cold coffee.")


def test_marking_escapes_what_was_typed():
    assert "<script>" not in mark_mistakes("<script> x", "She works.")


def test_punctuation_is_not_the_lesson():
    """A forgotten «?» or comma failed a sentence whose words were right."""
    assert matches("do you like coffee", "Do you like coffee?")
    assert matches("Yes I do", "Yes, I do.")
    assert matches("is it yours?", "Is it yours?")
    assert not matches("Do you likes coffee?", "Do you like coffee?")


def test_a_miss_keeps_what_was_typed():
    state = miss(CardState(typing=True), "  she   doesn'n like  ")
    assert state.attempt == 2
    assert state.last_typed == "she doesn'n like"
    assert CardState.from_dict(state.to_dict()).last_typed == "she doesn'n like"


def test_a_pasted_wall_of_text_is_capped():
    """Past Telegram's limits the edit — or the copy button — is refused and
    the miss does not show at all."""
    state = miss(CardState(typing=True), "word " * 400)
    assert len(state.last_typed) <= 256
    assert len(state.last_typed) <= LAST_TYPED_MAX + 1


def test_the_card_shows_the_marked_miss_and_says_how_to_fix_it():
    text = render_card(
        topic_title="T", score=None, ru="Фраза.", typing=True, attempt=2,
        last_miss_html="she <u><b>doesn&#x27;n</b></u> like",
    )
    assert "<u><b>doesn&#x27;n</b></u>" in text
    assert "скопирует" in text
    assert "Попытка 2 из 3" in text


def test_the_copy_button_appears_only_after_a_miss():
    assert _copies(constructor_typing_kb(7)) == []
    assert _copies(constructor_typing_kb(7, "she doesn'n like")) == ["she doesn'n like"]


def test_the_result_shows_the_learners_answer_marked():
    text = render_result(
        ru="Ф.", en="She doesn't live here.", correct=False, answer_credit=0.0,
        given_html="She <u><b>don&#x27;t</b></u> live here",
    )
    assert "ты: She <u><b>don&#x27;t</b></u> live here" in text
