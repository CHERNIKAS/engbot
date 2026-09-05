"""What the card says after the answer.

The verdict alone ("✅ Верно! 🎉") threw away everything the card was carrying:
which word it was, and whether the tap moved anything. These pin the reveal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import _in_days_phrase, _percent, _recap

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
TARGET = (9.5, 5)  # score bar, typed answers required


def _uw(score=5.0, typed=0, status=WordStatus.REVIEW.value, mastery=0.0, due_in=3):
    return SimpleNamespace(
        status=status,
        learning_score=score,
        production_count=typed,
        mastery_score=mastery,
        custom_translation=None,
        next_review_at=NOW + timedelta(days=due_in),
    )


def _word(writing="report", translation="отчёт", example="The report is on your desk."):
    return SimpleNamespace(writing=writing, translation=translation, example_sentence=example, level="A2")


def _lines(text: str) -> list[str]:
    return [ln for ln in text.split("\n") if ln]


# ---- the pair comes back ----


def test_a_correct_answer_names_the_word_but_not_its_translation():
    """The user just produced this pairing themselves — handing it back teaches
    nothing. The word alone stays as an anchor for the chat history."""
    out = _recap(_uw(), _word(), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "<b>report</b>" in out
    assert "отчёт" not in out


def test_a_miss_does_not_repeat_the_word_the_verdict_already_gave():
    """«❌ Мимо. Правильно: report» already says it — printing it again reads
    as a stutter, so the recap contributes only the translation."""
    out = _recap(_uw(), _word(), before_percent=42, was_mastered=False, correct=False, target=TARGET, now=NOW)
    assert "↳ отчёт" in out
    assert "<b>report</b>" not in out


def test_a_custom_translation_wins_over_the_catalogue_one():
    uw = _uw()
    uw.custom_translation = "докладная"
    out = _recap(uw, _word(), before_percent=42, was_mastered=False, correct=False, target=TARGET, now=NOW)
    assert "докладная" in out
    assert "отчёт" not in out


def test_a_word_with_no_translation_still_gets_its_anchor():
    out = _recap(_uw(), _word(translation=None), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "<b>report</b>" in out


# ---- the example is a consolation, not decoration ----


def test_the_example_shows_only_after_a_miss():
    hit = _recap(_uw(), _word(), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    miss = _recap(_uw(), _word(), before_percent=42, was_mastered=False, correct=False, target=TARGET, now=NOW)
    assert "desk" not in hit
    assert "desk" in miss


def test_no_example_no_line():
    out = _recap(_uw(), _word(example=None), before_percent=42, was_mastered=False, correct=False, target=TARGET, now=NOW)
    assert "📝" not in out


# ---- the tap has to move something visible ----


def test_progress_is_shown_as_before_and_after():
    out = _recap(_uw(score=6.0), _word(), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert f"🌱 42% → {_percent(_uw(score=6.0), TARGET)}%" in out


def test_a_percentage_that_did_not_move_is_printed_once():
    """A mastered-word refresher can leave the bar where it was; «60% → 60%»
    would look like a rendering bug."""
    uw = _uw(score=5.7)
    out = _recap(uw, _word(), before_percent=_percent(uw, TARGET), was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "→" not in out.split("🌱")[1].split("\n")[0]


def test_the_typed_requirement_is_named_only_once_it_is_the_last_thing_left():
    """Under a half-full bar it is one more number nobody asked for."""
    early = _recap(_uw(score=5.0, typed=0), _word(), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "✍️" not in early
    out = _recap(_uw(score=9.5, typed=2), _word(), before_percent=90, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "✍️ напечатать ещё 3 раза" in out


def test_the_typed_requirement_disappears_once_met():
    out = _recap(_uw(score=9.5, typed=5), _word(), before_percent=90, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "✍️" not in out


# ---- mastery is the one moment worth celebrating ----


def test_crossing_into_mastered_says_so():
    uw = _uw(status=WordStatus.MASTERED.value, mastery=1.0)
    out = _recap(uw, _word(), before_percent=95, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "Слово выучено!" in out
    assert "🌱" not in out


def test_an_already_mastered_word_reports_its_health_not_a_celebration():
    uw = _uw(status=WordStatus.MASTERED.value, mastery=3.5)
    out = _recap(uw, _word(), before_percent=100, was_mastered=True, correct=True, target=TARGET, now=NOW)
    assert "Выучено на 3.5 из 5" in out
    assert "Слово выучено!" not in out


# ---- when it comes back ----


def test_the_next_sighting_is_named():
    out = _recap(_uw(due_in=3), _word(), before_percent=42, was_mastered=False, correct=True, target=TARGET, now=NOW)
    assert "🔁 вернусь через 3 дн" in out


def test_days_phrasing():
    assert _in_days_phrase(NOW, NOW) == "сегодня"
    assert _in_days_phrase(NOW - timedelta(days=2), NOW) == "сегодня"  # overdue reads as now
    assert _in_days_phrase(NOW + timedelta(days=1), NOW) == "завтра"
    assert _in_days_phrase(NOW + timedelta(days=9), NOW) == "через 9 дн"
    assert _in_days_phrase(None, NOW) is None


# ---- shape ----


def test_the_block_starts_on_its_own_line_and_stays_short():
    out = _recap(_uw(), _word(), before_percent=42, was_mastered=False, correct=False, target=TARGET, now=NOW)
    assert out.startswith("\n")
    assert len(_lines(out)) <= 4  # translation, example, progress, next
