"""The periodic check: when it comes back, what passes, and what it reports."""
from __future__ import annotations

from app.domain.topic_test import (
    MAX_INTERVAL_DAYS,
    PASS_CORRECT,
    TEST_SIZE,
    next_interval_days,
    passed,
    render_offer,
    render_question,
    render_result,
)


def test_intervals_expand_as_the_topic_keeps_holding():
    """Something recalled after a longer gap is more firmly held, and asking
    sooner than necessary spends a card another topic needed."""
    seq = [next_interval_days(n) for n in range(5)]
    assert seq == sorted(seq)
    assert len(set(seq)) > 1


def test_a_failure_brings_the_next_check_back_in_close():
    """Leaving a shaky topic unchecked for two months is how it disappears."""
    assert next_interval_days(0) < next_interval_days(3)


def test_the_interval_is_capped():
    assert next_interval_days(99) == MAX_INTERVAL_DAYS


def test_the_bar_is_eight_of_ten():
    assert passed(PASS_CORRECT)
    assert not passed(PASS_CORRECT - 1)
    assert PASS_CORRECT < TEST_SIZE


def test_the_offer_states_the_cost_before_it_starts():
    """The learner's guess at how long it takes is what decides whether they
    start it, so guessing has to be unnecessary."""
    text = render_offer("Present Simple")
    assert str(TEST_SIZE) in text
    assert "подсказок не будет" in text


def test_the_question_shows_progress_through_the_block():
    """Five minutes of answering into silence is how a session gets abandoned
    halfway."""
    text = render_question("Present Simple", "Она работает.", index=3, correct_so_far=2)
    assert f"4 / {TEST_SIZE}" in text
    assert "✅ 2" in text


def test_the_report_lists_what_went_wrong_beside_what_was_expected():
    """A score alone says the learner is worse than they thought and nothing
    about why — and this is the only place these ten sentences appear
    together."""
    text = render_result(
        "Present Simple",
        correct=7,
        mistakes=[("Она работает.", "She work.", "She works.")],
        next_in_days=3,
    )
    assert "She work." in text and "She works." in text
    assert "просело" in text


def test_a_clean_run_needs_no_list_of_mistakes():
    text = render_result("T", correct=TEST_SIZE, mistakes=[], next_in_days=7)
    assert "держится" in text
    assert "Ошибки" not in text


def test_an_empty_answer_is_shown_as_a_dash_not_a_blank():
    """A blank line under «ты:» reads as a rendering bug."""
    text = render_result("T", correct=0, mistakes=[("Фраза.", "  ", "Phrase.")], next_in_days=3)
    assert "—" in text


def test_generated_content_cannot_break_the_report():
    text = render_result("T", correct=0, mistakes=[("<b>ru", "<i>x", "<u>en")], next_in_days=3)
    assert "<b>ru" not in text
    assert "&lt;b&gt;ru" in text
