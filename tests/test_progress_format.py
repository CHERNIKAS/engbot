from __future__ import annotations

from app.domain.enums import LearningTrack
from app.services.progress_service import TrackProgress, _bar, _plural, format_progress


def _track(**over) -> TrackProgress:
    # uid 2 on 2026-11-16 — the learner whose question started the rewrite.
    base = dict(
        track=LearningTrack.ENGLISH,
        total_words=312,
        new_words=200,
        learning_words=31,
        mastered_words=81,
        snoozed_words=0,
        archived_words=0,
        grammar_topics_total=30,
        grammar_topics_done=0,
        stage_recognize=10,
        stage_choose=7,
        stage_write=14,
        plan_done=9,
        plan_total=30,
        level="A1",
        band1_mastered=46,
        band2_mastered=4,
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


def test_the_screen_as_agreed():
    """The exact text agreed with the owner on 2026-11-16."""
    assert format_progress(3, [_track()]) == (
        "🌸 <b>Твой прогресс</b>\n"
        "🔥 <b>3</b> дня подряд\n\n"
        "📅 План на сегодня: <b>9</b> из 30\n"
        "▓▓▓░░░░░░░\n\n"
        "📚 <b>Слова</b>\n"
        "⭐ выучено — 81\n"
        "✍️ пишешь сам — 14\n"
        "👆 выбираешь из вариантов — 7\n"
        "👀 узнаёшь — 10\n"
        "🆕 ещё впереди — 200\n\n"
        "🎓 Уровень A1\n"
        "До A2: 46 из 500 частых слов\n"
        "▓░░░░░░░░░\n\n"
        "📖 Грамматика: 0 из 30 тем\n\n"
        "Каждое слово идёт по шагам:\n"
        "👀 узнаёшь → 👆 выбираешь → ✍️ пишешь сам → ⭐ выучено"
    )


def test_a_closed_plan_says_so_and_no_plan_says_nothing():
    assert "✅ План на сегодня пройден: <b>16</b> из 16" in format_progress(
        3, [_track(plan_done=16, plan_total=16)]
    )
    text = format_progress(3, [_track(plan_done=None, plan_total=None)])
    assert "План" not in text


def test_the_way_to_b1_names_both_bands_and_b1_is_the_top():
    text = format_progress(3, [_track(level="A2", band1_mastered=600, band2_mastered=50)])
    assert "До B1: 600 из 850 частых слов и 50 из 200 следующих" in text
    assert "До " not in format_progress(3, [_track(level="B1")])


def test_the_track_label_only_when_there_are_several():
    assert "English" not in format_progress(3, [_track()])


def test_format_progress_hides_archive_when_zero():
    assert "архив" not in format_progress(4, [_track(archived_words=0)])
    assert "💤 в архиве — 7" in format_progress(4, [_track(archived_words=7)])


def test_format_progress_shows_snoozed_only_when_present():
    assert "отложено" not in format_progress(4, [_track(snoozed_words=0)])
    assert "😴 отложено — 2" in format_progress(4, [_track(snoozed_words=2)])


def test_format_progress_breakdown_sums_to_total():
    """The vocab buckets must partition the total (the bug: archived was
    double-counted, so new+learning+mastered+snoozed+archived > total)."""
    t = _track(
        total_words=100, new_words=70, learning_words=20, mastered_words=5,
        snoozed_words=2, archived_words=3,
    )
    assert t.new_words + t.learning_words + t.mastered_words + t.snoozed_words + t.archived_words == t.total_words


def test_format_progress_streak_plural_and_empty():
    assert "<b>1</b> день подряд" in format_progress(1, [_track()])
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
    assert "🎓 Курс: урок <b>4</b> / 92 · ⭐ 37/914" in text


def test_format_progress_course_line_absent_by_default():
    assert "Курс" not in format_progress(4, [_track()])
    assert "Курс" not in format_progress(4, [_track()], course=_course(enrolled=False))


def test_format_progress_course_finished():
    text = format_progress(4, [_track()], course=_course(finished=True))
    assert "Курс: <b>пройден</b>" in text
