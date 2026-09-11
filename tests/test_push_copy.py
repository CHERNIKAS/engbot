"""The numbers and words a push card prints.

Mutation testing on the push helpers left the Russian plural of раз
completely unpinned (17 survivors), the typed-answer line free to say
"ещё 0 раз" once the requirement was met, and the exact percentage
unchecked -- the recap test computed its expectation with _percent itself.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import _mask_target, _percent, _progress_line, _times


def test_the_plural_of_raz():
    expected = {
        1: "раз", 2: "раза", 3: "раза", 4: "раза", 5: "раз", 10: "раз",
        11: "раз", 12: "раз", 14: "раз", 15: "раз", 21: "раз", 22: "раза",
        24: "раза", 25: "раз", 101: "раз", 111: "раз", 112: "раз", 122: "раза",
    }
    for n, word in expected.items():
        assert _times(n) == word, n


def test_the_percentage_is_the_share_of_the_bar():
    def pct(score, bar):
        return _percent(SimpleNamespace(learning_score=score), (bar, 5))

    assert pct(4.75, 9.5) == 50
    assert pct(9.5, 9.5) == 100
    assert pct(12.0, 9.5) == 100  # past the bar still reads as full
    assert pct(0.0, 9.5) == 0


def _uw(score, typed):
    return SimpleNamespace(
        status=WordStatus.REVIEW.value, mastery_score=0.0, learning_score=score,
        production_count=typed, mistakes_count=0, last_reviewed_at=None,
    )


def test_a_met_typing_requirement_is_not_mentioned():
    line = _progress_line(_uw(score=9.5, typed=5), target=(9.5, 5), typing_now=True)
    assert "✍️" not in line


def test_an_unmet_typing_requirement_is():
    line = _progress_line(_uw(score=9.5, typed=4), target=(9.5, 5), typing_now=True)
    assert "✍️ напечатать ещё 1 раз" in line


def test_no_typing_requirement_means_no_typing_line():
    line = _progress_line(_uw(score=9.5, typed=0), target=(9.5, 0), typing_now=True)
    assert "✍️" not in line


def test_nothing_to_mask_is_not_a_cloze():
    assert _mask_target("Some sentence here.", "") is None
    assert _mask_target("", "word") is None
