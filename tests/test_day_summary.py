"""The closing message: what it says, and what it refuses to say."""
from __future__ import annotations

from app.domain import day_plan as rules
from app.domain.day_summary import render, render_resized


def _counts(**kw):
    return {getattr(rules, k.upper()): v for k, v in kw.items()}


def test_a_line_with_nothing_in_it_is_not_printed():
    """A zero is noise, and a column of zeroes hides the two real numbers."""
    text = render(counts=_counts(repeat=19, new_word=2))
    assert "19" in text
    assert "фраз" not in text


def test_the_largest_number_earned_comes_first():
    """On most days repeats are the bulk of the work; making the learner hunt
    for it under the new words undersells the day."""
    text = render(counts=_counts(repeat=19, new_word=2, phrase=2))
    assert text.index("повторов") < text.index("новых слов")


def test_the_topic_score_is_shown_as_a_move_not_a_number():
    """A bare «4.1» says nothing about whether the day helped."""
    text = render(
        counts=_counts(grammar=4),
        topic_title="Present Simple",
        score_before=0.76,
        score_after=0.82,
    )
    assert "4.1" in text and "3.8" in text and "↑" in text


def test_a_score_that_did_not_move_is_not_dressed_up_as_progress():
    text = render(
        counts=_counts(grammar=4), topic_title="T", score_before=0.80, score_after=0.801
    )
    assert "↑" not in text and "↓" not in text


def test_a_slide_is_shown_honestly():
    text = render(counts=_counts(grammar=4), topic_title="T", score_before=0.9, score_after=0.7)
    assert "↓" in text


def test_a_streak_of_one_is_not_announced():
    """«🔥 серия 1 день» on the first finish makes the feature look like it is
    counting down."""
    assert "Серия" not in render(counts=_counts(repeat=1), streak_days=1)
    assert "Серия" in render(counts=_counts(repeat=1), streak_days=2)


def test_russian_plurals_hold():
    for n, word in ((2, "дня"), (5, "дней"), (21, "день"), (11, "дней"), (112, "дней")):
        assert word in render(counts=_counts(repeat=1), streak_days=n), n


def test_passing_a_topic_is_called_out():
    text = render(counts=_counts(grammar=4), topic_title="Артикли", score_after=0.95, topic_passed=True)
    assert "сдана" in text


def test_a_topic_title_cannot_break_the_message():
    text = render(counts=_counts(grammar=1), topic_title="<b>x", score_after=0.5, topic_passed=True)
    assert "<b>x" not in text


def test_an_empty_day_still_closes_cleanly():
    """A plan whose slots were all unfillable closes with nothing in it, and
    that must not render as a broken message."""
    assert "закрыт" in render(counts={})


def test_resizing_is_said_out_loud_in_both_directions():
    """A plan that silently grows looks broken: the day got longer and no
    reason was given."""
    assert "28 → 30" in render_resized(28, 30)
    assert "28 → 26" in render_resized(28, 26)


def test_shrinking_is_phrased_as_the_bot_adjusting():
    """Not as the learner falling behind — they already know they missed days."""
    text = render_resized(28, 26)
    assert "Снижаю" in text
