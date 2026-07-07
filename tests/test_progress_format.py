from __future__ import annotations

from app.domain.enums import LearningTrack
from app.services.progress_service import TrackProgress, _bar, _plural, format_progress


def _track(**over) -> TrackProgress:
    base = dict(
        track=LearningTrack.ENGLISH,
        studied_today=23,
        studied_today_words=14,
        studied_today_grammar=9,
        daily_goal=50,
        total_words=1574,
        new_words=1424,
        learning_words=120,
        mastered_words=0,
        weak_words=9,
        snoozed_words=0,
        archived_words=0,
        grammar_topics_total=17,
        grammar_topics_done=3,
        grammar_items_mastered=24,
        grammar_items_in_progress=8,
    )
    base.update(over)
    return TrackProgress(**base)


def test_plural_days():
    assert _plural(1, "день", "дня", "дней") == "день"
    assert _plural(2, "день", "дня", "дней") == "дня"
    assert _plural(4, "день", "дня", "дней") == "дня"
    assert _plural(5, "день", "дня", "дней") == "дней"
    assert _plural(11, "день", "дня", "дней") == "дней"
    assert _plural(21, "день", "дня", "дней") == "день"


def test_bar_caps_and_fills():
    assert _bar(0, 50) == "░" * 10
    assert _bar(50, 50) == "▓" * 10
    assert _bar(100, 50) == "▓" * 10  # capped, never overflows
    assert _bar(23, 50) == "▓" * 5 + "░" * 5  # round(10*23/50)=5
    assert _bar(5, 0) == "▓" * 10  # no goal -> full


def test_format_progress_counts_grammar_in_today():
    text = format_progress(4, [_track()])
    # The headline "today" must include grammar (23 = 14 words + 9 grammar).
    assert "Сегодня: <b>23</b> / 50" in text
    assert "🔤 слова: 14" in text
    assert "📖 грамматика: 9" in text


def test_format_progress_shows_grammar_block():
    text = format_progress(4, [_track()])
    assert "Грамматика — <b>3</b> / 17 тем" in text
    assert "упражнений: 24" in text
    assert "в работе: 8" in text


def test_format_progress_hides_archive_when_zero():
    assert "архив" not in format_progress(4, [_track(archived_words=0)])
    assert "💤 архив: 7" in format_progress(4, [_track(archived_words=7)])


def test_format_progress_shows_snoozed_only_when_present():
    assert "отложено" not in format_progress(4, [_track(snoozed_words=0)])
    assert "😴 отложено: 2" in format_progress(4, [_track(snoozed_words=2)])


def test_format_progress_breakdown_sums_to_total():
    """The vocab buckets must partition the total (the bug: archived was
    double-counted, so new+learning+mastered+snoozed+archived > total)."""
    t = _track(
        total_words=100, new_words=70, learning_words=20, mastered_words=5,
        snoozed_words=2, archived_words=3,
    )
    assert t.new_words + t.learning_words + t.mastered_words + t.snoozed_words + t.archived_words == t.total_words


def test_format_progress_streak_plural_and_empty():
    assert "1</b> день подряд" in format_progress(1, [_track()])
    assert "пусто" in format_progress(0, []).lower()


def _course(**over):
    from app.services.course_service import CourseProgress

    base = dict(
        enrolled=True,
        total_words=914,
        mastered_words=37,
        in_progress=21,
        current_lesson=4,
        total_lessons=92,
        level="A1",
        finished=False,
    )
    base.update(over)
    return CourseProgress(**base)


def test_format_progress_course_line_when_enrolled():
    text = format_progress(4, [_track()], course=_course())
    assert "🎓 Курс: урок <b>4</b> / 92 · A1 · ⭐ 37/914" in text


def test_format_progress_course_line_absent_by_default():
    assert "Курс" not in format_progress(4, [_track()])
    assert "Курс" not in format_progress(4, [_track()], course=_course(enrolled=False))


def test_format_progress_course_finished():
    text = format_progress(4, [_track()], course=_course(finished=True))
    assert "Курс: <b>пройден</b>" in text
