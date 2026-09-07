"""Card transparency: the progress line says how far along in words rather than
in fractions, names the gate still in the way, and keeps the misses and
last-seen that explain where the number came from."""
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
    assert "🌱 32%" in line
    assert "❌" not in line


def test_progress_line_shows_misses_and_last_seen():
    # the drag case: some score with 2 misses, last seen 9 days ago
    line = _progress_line(
        _uw(learning_score=2.0, mistakes=2, last=NOW - timedelta(days=9)),
        now=NOW,
        target=(9.5, 5),
    )
    assert "🌱 21%" in line
    assert "❌ ошибок: 2" in line
    assert "9 дн назад" in line


def test_mastered_word_shows_its_health_score_instead():
    line = _progress_line(
        _uw(status=WordStatus.MASTERED.value, score=4.2), now=NOW, target=(9.5, 5)
    )
    assert "⭐ Выучено на 4.2 из 5" in line
    assert "🌱" not in line


def test_progress_line_mastered_unchanged():
    line = _progress_line(_uw(status=WordStatus.MASTERED.value, score=4.2), now=NOW)
    assert line == "⭐ Выучено на 4.2 из 5"


def test_the_typed_line_disappears_once_the_requirement_is_met():
    """It's the gate in the way, not a permanent score. Saying "5 из 5" after
    the fact is noise on a card the user is trying to read quickly."""
    line = _progress_line(_uw(learning_score=8.0, production=5), now=NOW, target=(9.5, 5))
    assert "напечатать" not in line


def test_the_percentage_never_exceeds_a_hundred():
    line = _progress_line(_uw(learning_score=99.0, production=5), now=NOW, target=(9.5, 5))
    assert "🌱 100%" in line


def test_a_button_card_does_not_ask_for_typing():
    """Under four buttons and no text field, "напечатать ещё 3 раза" asks for
    something the user cannot do from where they're standing."""
    line = _progress_line(_uw(learning_score=4.5, production=2), now=NOW, target=(9.5, 5))
    assert "напечатать" not in line


def test_the_typing_card_does_ask():
    line = _progress_line(
        _uw(learning_score=4.5, production=2), now=NOW, target=(9.5, 5), typing_now=True
    )
    assert "напечатать ещё 3 раза" in line


def test_a_button_card_explains_a_stalled_hundred_percent():
    """Score full, production short — without the line, "100%" that never
    graduates looks broken."""
    line = _progress_line(_uw(learning_score=9.5, production=2), now=NOW, target=(9.5, 5))
    assert "🌱 100%" in line
    assert "напечатать ещё 3 раза" in line


# ---- grammar items ride the same progress line ----


def test_a_grammar_item_gets_a_progress_line_without_a_learning_score():
    """UserGrammarItem has no learning_score / production_count — it rides raw
    repetitions. Reading the word columns off one raised AttributeError inside
    card rendering, which aborted the whole push tick: grammar cards silently
    stopped being delivered at all."""
    ugi = SimpleNamespace(
        status="review",
        repetitions_count=3,
        mistakes_count=1,
        mastery_score=0.0,
        last_reviewed_at=None,
    )
    line = _progress_line(ugi, now=NOW)
    assert "🌱" in line
    assert "ошибок: 1" in line
