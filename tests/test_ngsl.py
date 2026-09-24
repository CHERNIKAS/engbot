"""What the corpus rank is allowed to claim about a word.

The rank decides what gets taught first, so a wrong answer here does not make
one card worse — it reorders the entire curriculum. The cases below are the
ones that were silently wrong under the old 1-to-5 guess.
"""
from __future__ import annotations

from app.domain.ngsl import headword, is_inflection, rank_of


def test_the_most_common_words_rank_at_the_top():
    assert rank_of("the") == 1
    assert rank_of("be") == 2


def test_rank_orders_words_the_old_buckets_could_not_separate():
    """`you` and `salad` shared bucket 1 under the guessed scale; `would` was
    absent from the catalogue entirely while `giggle` was being taught."""
    assert rank_of("you") < rank_of("year")
    assert rank_of("would") < 100


def test_an_inflection_ranks_as_its_headword():
    """Otherwise `drove` looks like an unknown word and gets taught separately
    from `drive`, which is how the catalogue grew 90 duplicate entries."""
    assert headword("drove") == "drive"
    assert rank_of("drove") == rank_of("drive")
    assert is_inflection("drove") is True


def test_a_headword_is_not_an_inflection_of_itself():
    assert is_inflection("drive") is False
    assert headword("drive") == "drive"


def test_off_list_words_report_no_rank_rather_than_the_worst_rank():
    """`apple` is absent because the corpus is general written English, not
    because it is rare or advanced. Treating None as "worst" would bury exactly
    the concrete vocabulary a beginner needs."""
    assert rank_of("apple") is None
    assert headword("apple") is None
    assert is_inflection("apple") is False


def test_phrases_and_blanks_have_no_rank():
    assert rank_of("nice to meet you") is None
    assert rank_of("") is None
    assert rank_of(None) is None


def test_lookup_ignores_case_and_padding():
    assert rank_of("  The ") == 1
    assert headword("DROVE") == "drive"
