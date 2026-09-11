"""The order in which the picker prefers words, pinned as an order.

The whole level rework exists because words did not fit the learner. Yet
mutation testing found the preference table free to change: making at-level
words rank the same as one-below survived the entire suite. These pin the
intended ladder of preference, not the numbers that encode it.
"""
from __future__ import annotations

from app.domain.levels import (
    DEFAULT_SOURCE_PRIORITY,
    SOURCE_PRIORITY,
    UNKNOWN_LEVEL_RANK,
    selection_rank,
)


def test_the_picker_prefers_words_in_this_order():
    """For a B1 learner: at level, then one easier, then one harder, then two
    easier, then two harder, then anything further out."""
    user = "B1"
    ladder = [
        selection_rank("B1", user),  # at level
        selection_rank("A2", user),  # one easier
        selection_rank("B2", user),  # one harder
        selection_rank("A1", user),  # two easier
        selection_rank("C1", user),  # two harder
        selection_rank("C2", user),  # three harder
    ]
    assert ladder == sorted(ladder)
    assert len(set(ladder)) == len(ladder), ladder


def test_far_below_ranks_with_far_above():
    """Three levels away is out of reach either way."""
    assert selection_rank("A1", "B2") == selection_rank("C2", "A2")
    assert selection_rank("A1", "B2") > selection_rank("A2", "B2")


def test_an_untagged_word_sits_between_one_easier_and_two_easier():
    user = "B1"
    assert selection_rank("A2", user) < UNKNOWN_LEVEL_RANK < selection_rank("A1", user)
    assert selection_rank(None, user) == UNKNOWN_LEVEL_RANK


def test_words_the_user_chose_come_before_course_and_packs():
    assert SOURCE_PRIORITY["manual"] == SOURCE_PRIORITY["txt_import"]
    assert SOURCE_PRIORITY["manual"] < SOURCE_PRIORITY["course"] < SOURCE_PRIORITY["pack"]
    assert DEFAULT_SOURCE_PRIORITY >= SOURCE_PRIORITY["course"]
