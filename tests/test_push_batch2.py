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
