from __future__ import annotations

import pytest

from app.domain.study_drill import (
    STAGE_QUIZ,
    STAGE_TYPE,
    DrillState,
    is_typing_correct,
    normalize_answer,
)


def test_new_starts_all_at_quiz():
    s = DrillState.new([10, 20, 30])
    assert s.total == 3
    assert s.current() == (10, STAGE_QUIZ)
    assert s.learned_count() == 0
    assert s.remaining_count() == 3


def test_new_dedupes_preserving_order():
    s = DrillState.new([10, 10, 20])
    assert s.total == 2
    assert [item[0] for item in s.queue] == [10, 20]


def test_correct_quiz_promotes_to_type_not_learned():
    s = DrillState.new([10])
    s.answer(True)  # quiz ok
    assert 10 not in s.learned
    assert s.current() == (10, STAGE_TYPE)


def test_correct_quiz_then_type_learns_word():
    s = DrillState.new([10])
    s.answer(True)  # quiz
    s.answer(True)  # type
    assert s.learned == [10]
    assert s.is_complete()
    assert s.remaining_count() == 0


def test_wrong_answer_requeues_same_stage_and_counts_mistake():
    s = DrillState.new([10, 20, 30])
    assert s.current() == (10, STAGE_QUIZ)
    s.answer(False)  # 10 wrong at quiz
    assert s.mistakes_for(10) == 1
    # 10 must reappear later still at quiz, not learned
    assert 10 not in s.learned
    stages = {item[0]: item[1] for item in s.queue}
    assert stages[10] == STAGE_QUIZ
    # next card is now 20 (10 was pushed back)
    assert s.current() == (20, STAGE_QUIZ)


def test_word_keeps_coming_back_until_correct():
    s = DrillState.new([10])
    s.answer(False)  # wrong quiz
    s.answer(False)  # wrong quiz again
    assert s.mistakes_for(10) == 2
    assert not s.is_complete()
    s.answer(True)  # quiz ok
    s.answer(True)  # type ok
    assert s.is_complete()
    assert s.learned == [10]


def test_skip_rotates_without_penalty():
    s = DrillState.new([10, 20])
    s.skip()
    assert s.current() == (20, STAGE_QUIZ)
    assert s.mistakes_for(10) == 0


def test_remove_current_drops_word_and_decrements_total():
    s = DrillState.new([10, 20])
    s.answer(True)  # 10 -> type (requeued behind 20)
    # current is 20 now
    assert s.current() == (20, STAGE_QUIZ)
    s.remove_current()  # remove 20 entirely
    assert s.total == 1
    assert all(item[0] != 20 for item in s.queue)


def test_full_session_simulation_two_words():
    s = DrillState.new([1, 2])
    # Drill until complete, always answering correctly.
    guard = 0
    while not s.is_complete() and guard < 20:
        s.answer(True)
        guard += 1
    assert s.is_complete()
    assert sorted(s.learned) == [1, 2]


def test_quiz_only_word_learned_after_single_quiz():
    s = DrillState.new([10], quiz_only=[10])
    assert s.current() == (10, STAGE_QUIZ)
    s.answer(True)  # quiz ok → learned directly, no TYPE stage for phrases
    assert s.learned == [10]
    assert s.is_complete()


def test_quiz_only_wrong_requeues_at_quiz():
    s = DrillState.new([10, 20], quiz_only=[10])
    s.answer(False)  # 10 wrong → back to quiz, not learned
    assert 10 not in s.learned
    restored = DrillState.from_dict(s.to_dict())
    assert restored.quiz_only == [10]


def test_serialization_roundtrip():
    s = DrillState.new([1, 2, 3])
    s.answer(True)
    s.answer(False)
    restored = DrillState.from_dict(s.to_dict())
    assert restored.queue == s.queue
    assert restored.learned == s.learned
    assert restored.mistakes == s.mistakes
    assert restored.total == s.total


@pytest.mark.parametrize(
    "typed,writing,ok",
    [
        ("hello", "hello", True),
        ("  Hello  ", "hello", True),
        ("HELLO", "hello", True),
        ("to run", "run", True),
        ("run", "to run", True),
        ("new   york", "new york", True),
        ("helo", "hello", False),
        ("", "hello", False),
        ("bye", "hello", False),
    ],
)
def test_is_typing_correct(typed: str, writing: str, ok: bool):
    assert is_typing_correct(typed, writing) is ok


def test_normalize_answer():
    assert normalize_answer("  To  Run ") == "run"
    assert normalize_answer("WELL-KNOWN") == "well-known"
