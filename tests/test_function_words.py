"""What the word rotation refuses to teach, and what it must keep teaching.

The flag is a hard filter in every picker, so a wrong entry here does not
degrade a card — it removes the word from the product entirely. These pin the
boundary in both directions.
"""
from __future__ import annotations

import pytest

from app.domain.function_words import FUNCTION_WORDS, is_function_word


@pytest.mark.parametrize(
    "word",
    [
        "the", "a", "an",           # nothing to pick
        "of", "to", "with", "as",   # sense depends on what follows
        "is", "been", "does",       # tense and person, not meaning
        "must", "would", "should",  # the modal-verbs topic
        "which", "whose",           # question order, not recall
        "some", "much", "every",    # the much/many/some/any topic
        "don't", "it's",            # negated auxiliaries
    ],
)
def test_grammar_owns_these(word):
    assert is_function_word(word) is True


@pytest.mark.parametrize(
    "word",
    [
        # Numbers are exact pairs and have their own topic to fill. The flag is
        # a hard filter, so listing them would empty that topic.
        "one", "two", "seven", "ten",
        # Ordinary vocabulary that merely looks small.
        "go", "say", "know", "get", "time", "good", "people", "work", "way",
        # Content words that merely begin like a function word.
        "understand", "instead", "however", "therefore",
    ],
)
def test_vocabulary_keeps_these(word):
    assert is_function_word(word) is False


def test_a_phrase_is_never_a_function_word():
    """Phrasebook entries are built out of function words — «a lot of» is an
    item to learn whole, not the sum of three excluded pieces."""
    assert is_function_word("a lot of") is False
    assert is_function_word("in front of") is False


def test_matching_ignores_case_and_padding():
    assert is_function_word("  The ") is True
    assert is_function_word("MUST") is True


def test_blank_input_is_not_a_function_word():
    assert is_function_word("") is False
    assert is_function_word(None) is False


def test_the_list_stays_small_enough_to_be_a_stoplist():
    """A stoplist that grows into the hundreds stops being a stoplist and
    starts being a curriculum decision nobody reviewed."""
    assert len(FUNCTION_WORDS) < 250
