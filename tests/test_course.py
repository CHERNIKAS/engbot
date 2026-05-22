from __future__ import annotations

from app.domain.course import current_lesson, total_lessons, words_to_add


def test_total_lessons():
    assert total_lessons(0) == 0
    assert total_lessons(10) == 1
    assert total_lessons(11) == 2
    assert total_lessons(561) == 57  # ceil(561/10)


def test_current_lesson():
    assert current_lesson(0, 0) == 0
    assert current_lesson(0, 50) == 1
    assert current_lesson(9, 50) == 1
    assert current_lesson(10, 50) == 2
    # all mastered → clamp to the last lesson, never overflow
    assert current_lesson(50, 50) == 5


def test_words_to_add_from_empty():
    spine = [1, 2, 3, 4, 5]
    assert words_to_add(spine, {}, 3) == [1, 2, 3]


def test_words_to_add_tops_up_deficit():
    spine = [1, 2, 3, 4, 5]
    # 2 in progress, goal 3 → add 1 next not-owned
    assert words_to_add(spine, {1: "learning", 2: "new"}, 3) == [3]


def test_words_to_add_ignores_mastered_for_capacity():
    spine = [1, 2, 3, 4, 5]
    # mastered doesn't occupy a slot → in_progress=1, need=2
    assert words_to_add(spine, {1: "mastered", 2: "learning"}, 3) == [3, 4]


def test_words_to_add_pipeline_full():
    spine = [1, 2, 3, 4, 5]
    assert words_to_add(spine, {1: "new", 2: "new", 3: "new"}, 3) == []


def test_words_to_add_spine_exhausted():
    assert words_to_add([1, 2], {}, 5) == [1, 2]


def test_words_to_add_goal_zero():
    assert words_to_add([1, 2, 3], {}, 0) == []
