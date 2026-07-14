"""Card transparency: progress line spells out misses + last-seen."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import _days_ago_phrase, _progress_line

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def _uw(reps=2, mistakes=0, status=WordStatus.REVIEW.value, last=None, score=0.0):
    return SimpleNamespace(
        repetitions_count=reps, mistakes_count=mistakes, status=status,
        last_reviewed_at=last, mastery_score=score,
    )


def test_days_ago_phrase():
    assert _days_ago_phrase(NOW, NOW) == "сегодня"
    assert _days_ago_phrase(NOW - timedelta(days=1), NOW) == "вчера"
    assert _days_ago_phrase(NOW - timedelta(days=9), NOW) == "9 дн назад"
    assert _days_ago_phrase(None, NOW) is None


def test_progress_line_plain_when_clean():
    line = _progress_line(_uw(reps=3, mistakes=0, last=None), now=NOW)
    assert "🌱 3 / 10" in line
    assert "❌" not in line


def test_progress_line_shows_misses_and_last_seen():
    # the drag case: 2/10 with 2 misses, last seen 9 days ago
    line = _progress_line(_uw(reps=2, mistakes=2, last=NOW - timedelta(days=9)), now=NOW)
    assert "🌱 2 / 10" in line
    assert "❌ 2" in line
    assert "9 дн назад" in line


def test_progress_line_mastered_unchanged():
    line = _progress_line(_uw(status=WordStatus.MASTERED.value, score=4.2), now=NOW)
    assert line == "⭐ 4.2 / 5"
