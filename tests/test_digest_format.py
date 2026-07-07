"""Weekly digest rendering: accuracy math, delta vs first-run, optional lines."""
from __future__ import annotations

from app.services.digest_service import WeekStats, format_digest


def _stats(**overrides) -> WeekStats:
    base = dict(
        words_correct=40,
        words_wrong=5,
        grammar_correct=10,
        grammar_wrong=5,
        mastered_total=12,
        mastered_delta=3,
        streak_days=9,
        hardest=("gaze", 3),
    )
    base.update(overrides)
    return WeekStats(**base)


def test_accuracy_and_answers_counts():
    s = _stats()
    assert s.answers == 60
    assert s.accuracy == 83  # 50/60


def test_full_digest_has_all_lines():
    text = format_digest(_stats())
    assert "60" in text and "83%" in text
    assert "+3" in text and "12" in text
    assert "9" in text  # streak
    assert "gaze" in text


def test_first_digest_shows_total_without_delta():
    text = format_digest(_stats(mastered_delta=None))
    assert "+3" not in text
    assert "Выучено всего" in text


def test_zero_delta_falls_back_to_total():
    text = format_digest(_stats(mastered_delta=0))
    assert "+0" not in text


def test_streak_and_hardest_lines_optional():
    text = format_digest(_stats(streak_days=0, hardest=None))
    assert "Серия" not in text
    assert "орешек" not in text


def test_accuracy_zero_answers_no_crash():
    s = _stats(words_correct=0, words_wrong=0, grammar_correct=0, grammar_wrong=0)
    assert s.accuracy == 0
