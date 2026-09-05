"""The offline generator's gates. It never runs in production, but everything it
lets through is baked into a migration, so a gate that silently passes
everything ships bad content that nothing downstream will catch."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gen_examples import (
    check,
    contains_word,
    word_pattern,
)

LEXICON = {"reliable": "B1", "concerning": "B2", "cat": "A1", "sit": "A1", "mat": "A1"}


def _row(sentence: str, hint_en: str = "A small animal sits here.", hint_ru: str = "Тут сидит зверёк."):
    return {"sentence": sentence, "hint_en": hint_en, "hint_ru": hint_ru}


def _word(w: str, lvl: str = "A1"):
    return {"w": w, "lvl": lvl, "t": "перевод"}


# ---- the pattern both checks share ----


def test_the_pattern_matches_a_whole_word_and_its_endings():
    assert contains_word("The cat sits on the mat.", "cat")
    assert contains_word("He goes home now.", "go")
    assert contains_word("She walked away quickly.", "walk")


def test_the_pattern_does_not_match_inside_another_word():
    """The first cut had literal backspace characters where the word boundaries
    were meant, so it matched nothing at all and its check passed everything."""
    assert not contains_word("He is going home.", "o")
    assert not contains_word("The category is wide.", "cat")


def test_masking_replaces_the_word_and_leaves_the_rest():
    masked = word_pattern("cat").sub("___", "The cat sits on the mat.")
    assert masked == "The ___ sits on the mat."


# ---- the gates themselves ----


def test_a_good_example_passes():
    assert check(_row("The cat sits on the mat."), _word("cat"), LEXICON) == []


def test_an_example_without_the_word_is_rejected():
    problems = check(_row("A small animal sleeps here."), _word("cat"), LEXICON)
    assert any("нет слова" in p for p in problems)


def test_a_phrase_that_masks_down_to_nothing_is_rejected():
    """"It's around the corner" as its own example blanks to "___." — a cloze
    card with nothing left to infer from."""
    phrase = "It's around the corner"
    problems = check(_row(f"{phrase}."), _word(phrase, "A2"), LEXICON)
    assert any("восстановить не по чему" in p for p in problems)


def test_a_hint_containing_the_word_is_rejected_as_a_spoiler():
    problems = check(
        _row("The cat sits on the mat.", hint_en="The cat is here."), _word("cat"), LEXICON
    )
    assert any("спойлер" in p for p in problems)


def test_vocabulary_above_the_word_level_is_rejected_in_both_fields():
    for row in (
        _row("The cat sits concerning the mat."),
        _row("The cat sits on the mat.", hint_en="A note concerning animals."),
    ):
        problems = check(row, _word("cat"), LEXICON)
        assert any("сложнее уровня" in p for p in problems), row


def test_hints_only_mode_ignores_the_throwaway_sentence():
    """Words that already have a hand-written example need only the hint;
    judging the sentence would reject good hints for a field never written."""
    row = _row("nonsense that contains no target at all")
    assert check(row, _word("cat"), LEXICON, hints_only=True) == []
    assert check(row, _word("cat"), LEXICON, hints_only=False) != []
