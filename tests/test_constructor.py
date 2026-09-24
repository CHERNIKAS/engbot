"""What the constructor accepts, what it pays, and what the score remembers.

The exercise exists because four options give a 25% floor from guessing. Most
of these guard the ways that floor could sneak back in — by forgiving the one
character that is the lesson, or by letting a score say "learned" long after it
stopped being true.
"""
from __future__ import annotations

from app.domain.constructor import (
    DECAY,
    MAX_ATTEMPTS,
    MIN_CREDIT,
    assembled,
    attempts_left,
    credit,
    full_answer,
    is_complete,
    matches,
    normalize,
    slot_correct,
    slot_options,
    stars,
    update_score,
)

SLOTS = [
    {"correct": "She", "options": ["She", "They", "I"]},
    {"correct": "doesn't", "options": ["doesn't", "don't", "didn't"]},
    {"correct": "live here.", "options": ["live here.", "lives here."]},
]
EN = "She doesn't live here."
ALTS = ["She does not live here."]


def test_the_things_that_are_not_the_lesson_are_ignored():
    """Case, spacing, a missing full stop and the curly apostrophe a phone
    inserts are not what is being tested."""
    assert matches("she doesn't live here", EN, ALTS)
    assert matches("  She   doesn’t live here.  ", EN, ALTS)
    assert matches("SHE DOESN'T LIVE HERE!", EN, ALTS)


def test_a_spelled_out_contraction_is_accepted():
    """Writing it formally is not an error, and being marked wrong for it is
    the fastest way to lose trust in the checker."""
    assert matches("She does not live here.", EN, ALTS)


def test_the_one_character_that_is_the_lesson_is_not_forgiven():
    """`don't` against `doesn't` is a single edit away, and it is the entire
    exercise. Any fuzzy matching here forgives exactly what is being taught."""
    assert not matches("She don't live here.", EN, ALTS)
    assert not matches("She doesn't lives here.", EN, ALTS)


def test_word_order_is_not_forgiven_either():
    assert not matches("Here she doesn't live.", EN, ALTS)


def test_an_empty_answer_is_never_a_match():
    assert not matches("", EN, ALTS)
    assert not matches(None, EN, ALTS)
    assert not matches("   ", EN, ALTS)


def test_an_answer_is_worth_less_on_each_further_attempt():
    assert credit(1) > credit(2) > credit(3)
    assert credit(1) == 1.0


def test_a_hint_costs_value_rather_than_blocking():
    """Using one is a legitimate route through; it just proves less."""
    assert credit(1, hinted=True) < credit(1)
    assert credit(1, hinted=True) > 0


def test_an_answer_that_landed_is_never_worth_nothing():
    """Otherwise someone who needs three attempts and a hint every time sits at
    a flat zero with no way to see themselves improving."""
    assert credit(3, hinted=True) >= MIN_CREDIT


def test_past_the_last_attempt_nothing_is_earned():
    """The sentence has been shown by then — there is nothing left to prove."""
    assert credit(MAX_ATTEMPTS + 1) == 0.0
    assert attempts_left(MAX_ATTEMPTS) == 0
    assert attempts_left(1) == MAX_ATTEMPTS - 1


def test_a_new_topic_starts_at_zero_and_climbs():
    score = update_score(None, 1.0)
    assert 0 < score < 1
    assert stars(score) < 5


def test_the_score_follows_recent_answers_instead_of_accumulating():
    """A running total can only go up, so a topic passed in March still reads
    as passed in September. This has to be able to fall."""
    score = 0.9
    for _ in range(20):
        score = update_score(score, 0.0)
    assert score < 0.1


def test_sustained_correct_answers_approach_full_marks():
    score = 0.0
    for _ in range(60):
        score = update_score(score, 1.0)
    assert stars(score) >= 4.5


def test_one_bad_answer_does_not_wipe_a_good_topic():
    """Reacting to a single miss would make the number twitch and stop being
    readable as a level."""
    score = 0.9
    after = update_score(score, 0.0)
    assert after > 0.7


def test_stars_stay_inside_the_scale_whatever_arrives():
    assert stars(None) == 0.0
    assert stars(-5) == 0.0
    assert stars(99) == 5.0


def test_decay_is_a_calibration_knob_not_a_hidden_constant():
    fast = update_score(0.0, 1.0, decay=0.5)
    slow = update_score(0.0, 1.0, decay=0.05)
    assert fast > slow > 0
    assert 0 < DECAY < 1


def test_slots_build_the_sentence_the_typing_mode_expects():
    """The two modes must agree, or the assisted one teaches a sentence the
    checker rejects."""
    assert matches(full_answer(SLOTS), EN, ALTS)


def test_walking_the_slots():
    assert slot_options(SLOTS, 0) == ["She", "They", "I"]
    assert slot_correct(SLOTS, 1) == "doesn't"
    assert assembled(SLOTS, ["She", "doesn't"]) == "She doesn't"
    assert not is_complete(SLOTS, ["She", "doesn't"])
    assert is_complete(SLOTS, ["She", "doesn't", "live here."])


def test_reading_past_the_end_is_empty_rather_than_an_error():
    """The last tap moves the index past the final slot; that path must not
    raise on a card the learner just finished."""
    assert slot_options(SLOTS, 99) == []
    assert slot_correct(SLOTS, 99) == ""
    assert slot_options([], 0) == []
    assert not is_complete([], [])


def test_normalize_is_stable_on_nothing():
    assert normalize(None) == ""
    assert normalize("") == ""
