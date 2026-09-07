"""Batch 2 push fixes: push-day rolls at window start; cloze-answer heuristic."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.push_service import _looks_like_cloze_answer, _push_day

MSK = ZoneInfo("Europe/Moscow")


def _msk(y, m, d, h):
    return datetime(y, m, d, h, 0, tzinfo=MSK)


# ---- overnight window: push-day must not roll at midnight ----

def test_push_day_overnight_stays_one_session_across_midnight():
    ws = 16  # window 16→02
    before = _push_day(_msk(2026, 7, 8, 23), ws)   # 23:00 day 8
    after = _push_day(_msk(2026, 7, 9, 1), ws)     # 01:00 day 9 (same session)
    assert before == after == "2026-07-08"


def test_push_day_overnight_new_session_at_window_start():
    ws = 16
    tail = _push_day(_msk(2026, 7, 9, 1), ws)      # early morning = prev session
    new = _push_day(_msk(2026, 7, 9, 16), ws)      # 16:00 = new session
    assert tail == "2026-07-08"
    assert new == "2026-07-09"


def test_push_day_daytime_window_rolls_at_open():
    ws = 10  # window 10→22
    assert _push_day(_msk(2026, 7, 8, 9), ws) == "2026-07-07"   # before open
    assert _push_day(_msk(2026, 7, 8, 10), ws) == "2026-07-08"  # at open


# ---- cloze answer heuristic: don't eat quick-add text ----

def test_cloze_accepts_single_english_word():
    assert _looks_like_cloze_answer("become")
    assert _looks_like_cloze_answer("  Become ")
    assert _looks_like_cloze_answer("don't")
    assert _looks_like_cloze_answer("well-known")


def test_cloze_rejects_quick_add_shapes():
    assert not _looks_like_cloze_answer("serendipity - прозорливость")
    assert not _looks_like_cloze_answer("become стать")        # two words
    assert not _looks_like_cloze_answer("hello, world")
    assert not _looks_like_cloze_answer("стать")               # cyrillic = a translation
    assert not _looks_like_cloze_answer("word\nword")
    assert not _looks_like_cloze_answer("")


# ---- what counts as a typed answer to a type-in card ----

from app.services.push_service import (  # noqa: E402
    CARD_CLOZE,
    CARD_TYPE_IN,
    _looks_like_typed_answer,
)


def test_a_phrase_is_a_valid_type_in_answer():
    """The cloze rule (one English word) would reject every phrase answer."""
    assert _looks_like_typed_answer("Is it far from here?", CARD_TYPE_IN)
    assert _looks_like_typed_answer("  see you later ", CARD_TYPE_IN)


def test_a_quick_add_is_still_a_quick_add():
    """Eating «serendipity - прозорливость» as a wrong answer would delete the
    user's message and mark the card failed."""
    for text in ("serendipity - прозорливость", "serendipity | прозорливость", "a\nb"):
        assert not _looks_like_typed_answer(text, CARD_TYPE_IN)


def test_russian_text_is_not_an_answer():
    assert not _looks_like_typed_answer("далеко ли отсюда", CARD_TYPE_IN)


def test_empty_and_punctuation_only_are_not_answers():
    assert not _looks_like_typed_answer("   ", CARD_TYPE_IN)
    assert not _looks_like_typed_answer("???", CARD_TYPE_IN)


def test_a_multi_word_answer_to_a_blank_is_graded_not_filed_away():
    """A blank holds one token, so "might be" is a WRONG answer — but it is an
    answer. Sending it to quick-add left the card in flight, still nudging,
    and put an unwanted «Добавить "might be"?» prompt in the chat."""
    assert _looks_like_typed_answer("might be", CARD_CLOZE)
    assert _looks_like_typed_answer("become", CARD_CLOZE)


def test_a_quick_add_is_not_eaten_by_a_cloze_either():
    assert not _looks_like_typed_answer("serendipity - прозорливость", CARD_CLOZE)
    assert not _looks_like_typed_answer("стать", CARD_CLOZE)
