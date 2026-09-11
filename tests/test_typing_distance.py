"""The typo forgiveness behind typed answers.

_levenshtein was only ever reached through a yes/no of at most one edit,
so mutants that miscount distances survived on the handful of words tested.
And the four-letter threshold where forgiveness starts was never probed at
exactly four letters.
"""
from __future__ import annotations

from app.domain.study_drill import _levenshtein, is_typing_correct


def test_edit_distance_on_known_pairs():
    assert _levenshtein("kitten", "sitting") == 3
    assert _levenshtein("flaw", "lawn") == 2
    assert _levenshtein("ab", "ba") == 2
    assert _levenshtein("abc", "") == 3
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("", "") == 0
    assert _levenshtein("same", "same") == 0


def test_a_four_letter_word_forgives_one_typo():
    assert is_typing_correct("hape", "hope")
    assert is_typing_correct("hause", "house")


def test_a_three_letter_word_does_not():
    """One edit on a short word is a different word, cat and car."""
    assert not is_typing_correct("car", "cat")
