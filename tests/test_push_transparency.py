"""Card transparency: the progress line spells out BOTH mastery gates plus the
misses and last-seen that explain where the number came from."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import _days_ago_phrase, _progress_line

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def _uw(
    reps=2,
    mistakes=0,
    status=WordStatus.REVIEW.value,
    last=None,
    score=0.0,
    learning_score=0.0,
    production=0,
):
    return SimpleNamespace(
        repetitions_count=reps, mistakes_count=mistakes, status=status,
        last_reviewed_at=last, mastery_score=score,
        learning_score=learning_score, production_count=production,
    )


def test_days_ago_phrase():
    assert _days_ago_phrase(NOW, NOW) == "сегодня"
    assert _days_ago_phrase(NOW - timedelta(days=1), NOW) == "вчера"
    assert _days_ago_phrase(NOW - timedelta(days=9), NOW) == "9 дн назад"
    assert _days_ago_phrase(None, NOW) is None


def test_progress_line_plain_when_clean():
    line = _progress_line(
        _uw(learning_score=3.0, mistakes=0, last=None), now=NOW, target=(9.5, 5)
    )
    assert "🌱 3.0 / 9.5" in line
    assert "❌" not in line


def test_progress_line_shows_misses_and_last_seen():
    # the drag case: some score with 2 misses, last seen 9 days ago
    line = _progress_line(
        _uw(learning_score=2.0, mistakes=2, last=NOW - timedelta(days=9)),
        now=NOW,
        target=(9.5, 5),
    )
    assert "🌱 2.0 / 9.5" in line
    assert "❌ 2" in line
    assert "9 дн назад" in line


def test_progress_line_shows_the_typed_requirement():
    """The gate a user could otherwise never see: score alone never graduates
    a word, so the pen counter has to be on the card from the first answer."""
    line = _progress_line(
        _uw(learning_score=8.0, production=2), now=NOW, target=(9.5, 5)
    )
    assert "✍️ 2 / 5" in line


def test_mastered_word_shows_its_health_score_instead():
    line = _progress_line(
        _uw(status=WordStatus.MASTERED.value, score=4.2), now=NOW, target=(9.5, 5)
    )
    assert "⭐ 4.2 / 5" in line
    assert "🌱" not in line


def test_progress_line_mastered_unchanged():
    line = _progress_line(_uw(status=WordStatus.MASTERED.value, score=4.2), now=NOW)
    assert line == "⭐ 4.2 / 5"
