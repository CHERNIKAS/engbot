from __future__ import annotations

from app.domain.mastery import (
    MIN_PRODUCTION,
    RECOGNITION,
    REVERSE,
    TYPED_EXACT,
    TYPED_GRAMMAR,
    TYPED_SYNONYM,
    TYPED_TYPO,
    WRONG,
    apply_credit,
    credit,
    is_mastered,
    is_production,
    target_for,
)


# ---- what an answer is worth ----


def test_producing_a_word_is_worth_more_than_recognising_it():
    assert credit(TYPED_EXACT) > credit(REVERSE) > credit(RECOGNITION)


def test_near_misses_sit_between_right_and_wrong():
    for kind in (TYPED_TYPO, TYPED_SYNONYM, TYPED_GRAMMAR):
        assert credit(WRONG) < credit(kind) < credit(TYPED_EXACT)


def test_a_typo_counts_for_more_than_a_grammar_slip():
    """A slip on a long word means they know it; the wrong form means they
    half-know it."""
    assert credit(TYPED_TYPO) > credit(TYPED_GRAMMAR)


def test_an_unknown_kind_scores_nothing_rather_than_guessing():
    assert credit("something_new") == 0.0


def test_wrong_answers_cost_score():
    assert credit(WRONG) < 0


# ---- production ----


def test_only_typed_answers_count_as_production():
    assert is_production(TYPED_EXACT)
    assert is_production(TYPED_TYPO)
    assert is_production(TYPED_GRAMMAR)  # they wrote the word, just wrapped it wrong
    assert not is_production(RECOGNITION)
    assert not is_production(REVERSE)
    assert not is_production(WRONG)


def test_a_synonym_is_not_production_of_this_word():
    """They produced *a* word, not the one being taught."""
    assert not is_production(TYPED_SYNONYM)


# ---- the score itself ----


def test_score_accumulates():
    score = 0.0
    for kind in (RECOGNITION, RECOGNITION, TYPED_EXACT):
        score = apply_credit(score, kind)
    assert score == 2.5


def test_score_never_goes_negative():
    score = 0.0
    for _ in range(5):
        score = apply_credit(score, WRONG)
    assert score == 0.0


def test_score_avoids_floating_point_drift():
    score = 0.0
    for _ in range(10):
        score = apply_credit(score, RECOGNITION)
    assert score == 5.0


# ---- the mastery gates ----


def test_harder_words_need_more():
    easy_score, easy_prod = target_for("A1", "B1")
    at_score, at_prod = target_for("B1", "B1")
    hard_score, hard_prod = target_for("B2", "B1")
    assert easy_score < at_score < hard_score
    assert easy_prod <= at_prod <= hard_prod


def test_production_floor_holds_even_for_the_easiest_word():
    for word_level in ("A1", "A2", "B1", "B2", "C1"):
        _score, production = target_for(word_level, "C1")
        assert production >= MIN_PRODUCTION


def test_choice_cards_alone_never_master_a_word():
    """The whole point: a word cannot graduate on guessable cards."""
    score = 0.0
    for _ in range(50):
        score = apply_credit(score, RECOGNITION)
    assert not is_mastered(score, production_count=0, word_level="B1", user_level="B1")


def test_enough_score_and_enough_production_masters_it():
    target_score, needed = target_for("B1", "B1")
    assert is_mastered(target_score, needed, "B1", "B1")


def test_production_without_the_score_is_not_enough_either():
    _target_score, needed = target_for("B1", "B1")
    assert not is_mastered(0.0, needed, "B1", "B1")


def test_untagged_word_is_graded_as_at_level():
    assert target_for(None, "B1") == target_for("B1", "B1")


def test_a_word_below_the_user_graduates_sooner_than_one_above():
    easy_score, easy_prod = target_for("A1", "B1")
    hard_score, hard_prod = target_for("C1", "B1")
    assert is_mastered(easy_score, easy_prod, "A1", "B1")
    assert not is_mastered(easy_score, easy_prod, "C1", "B1")
    assert is_mastered(hard_score, hard_prod, "C1", "B1")


# ---- words that can never be typed ----


def test_a_phrase_that_cannot_be_typed_still_graduates_on_score():
    """"Is it far from here?" is already a whole sentence — there is nowhere to
    blank it out inside another one, so it can never earn a typed answer.
    Holding it to the production floor would make it unlearnable."""
    target_score, _needed = target_for("A2", "A2")
    assert is_mastered(target_score, 0, "A2", "A2", production_possible=False)


def test_waiving_production_does_not_waive_the_score():
    assert not is_mastered(0.0, 0, "A2", "A2", production_possible=False)


def test_the_floor_still_applies_wherever_typing_is_possible():
    target_score, _needed = target_for("A2", "A2")
    assert not is_mastered(target_score, 0, "A2", "A2", production_possible=True)
