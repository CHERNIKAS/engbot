"""Walking through one exercise: taps, mistakes, undo, hints.

The state is round-tripped through Redis between every tap, so the two things
worth guarding are that transitions do not mutate in place (which would work
locally and vanish on the way out) and that none of the escape hatches — undo,
hint, a second hint — can be used to get full credit for free.
"""
from __future__ import annotations

from app.domain.constructor import (
    MAX_ATTEMPTS,
    CardState,
    choose,
    credit,
    hint_prefix,
    miss,
    to_typing,
    undo,
    use_hint,
)

SLOTS = [
    {"correct": "She", "options": ["She", "They", "I"]},
    {"correct": "doesn't", "options": ["doesn't", "don't", "didn't"]},
    {"correct": "live here.", "options": ["live here.", "lives here."]},
]


def test_a_correct_tap_advances_to_the_next_slot():
    state, ok = choose(CardState(), SLOTS, 0)
    assert ok
    assert state.chosen == ("She",)
    assert state.slot_index == 1
    assert state.attempt == 1


def test_a_wrong_tap_costs_an_attempt_and_leaves_the_slot_open():
    """Writing the wrong piece into the sentence and judging at the end would
    walk the learner through a sentence they already know is broken."""
    state, ok = choose(CardState(), SLOTS, 1)  # "They"
    assert not ok
    assert state.chosen == ()
    assert state.slot_index == 0
    assert state.attempt == 2


def test_the_right_piece_after_a_wrong_one_still_lands():
    state, _ = choose(CardState(), SLOTS, 1)
    state, ok = choose(state, SLOTS, 0)
    assert ok
    assert state.chosen == ("She",)
    assert state.attempt == 2  # the mistake is not forgotten


def test_the_slot_that_actually_tests_the_rule():
    """After «She» the learner still has to know it takes «doesn't». No amount
    of elimination reveals that — which is the whole reason the assisted mode
    is not just a slower multiple choice."""
    state, _ = choose(CardState(), SLOTS, 0)
    state, wrong = choose(state, SLOTS, 1)  # "don't"
    assert not wrong
    state, right = choose(state, SLOTS, 0)  # "doesn't"
    assert right


def test_an_out_of_range_tap_changes_nothing():
    """A stale card from an earlier day can still be tapped."""
    state = CardState(chosen=("She",))
    after, ok = choose(state, SLOTS, 99)
    assert not ok
    assert after == state


def test_undo_takes_back_a_piece_but_not_the_attempts():
    """Refunding them would make «Ой, ошибся» a free retry."""
    state, _ = choose(CardState(), SLOTS, 1)  # wrong, attempt 2
    state, _ = choose(state, SLOTS, 0)  # "She"
    back = undo(state)
    assert back.chosen == ()
    assert back.attempt == 2


def test_undo_on_an_untouched_card_is_harmless():
    assert undo(CardState()) == CardState()


def test_a_second_hint_does_not_halve_the_value_twice():
    """Nothing stops the learner tapping it again, and the card should not
    quietly punish them for it."""
    once = use_hint(CardState())
    twice = use_hint(once)
    assert once == twice
    assert credit(1, hinted=twice.hinted) == credit(1, hinted=once.hinted)


def test_a_hint_is_cheaper_than_a_wrong_attempt():
    """Otherwise the rational move is to guess rather than ask, which is the
    opposite of what a hint is for."""
    assert credit(1, hinted=True) >= credit(2)


def test_attempts_run_out():
    state = CardState()
    for _ in range(MAX_ATTEMPTS):
        state = miss(state)
    assert state.exhausted
    assert credit(state.attempt) == 0.0


def test_transitions_never_mutate_in_place():
    """The state goes through Redis between taps; an in-place helper would
    appear to work and then drop the change on serialisation."""
    original = CardState(chosen=("She",), attempt=1)
    snapshot = original.to_dict()
    choose(original, SLOTS, 0)
    undo(original)
    use_hint(original)
    miss(original)
    to_typing(original)
    assert original.to_dict() == snapshot


def test_state_survives_a_round_trip():
    state = CardState(chosen=("She", "doesn't"), attempt=2, hinted=True, typing=True)
    assert CardState.from_dict(state.to_dict()) == state


def test_a_missing_state_reads_as_a_fresh_card():
    """Redis can drop the key; the card must not crash on the next tap."""
    assert CardState.from_dict(None) == CardState()
    assert CardState.from_dict({}) == CardState()


def test_the_hint_reaches_the_word_that_decides():
    """One word is almost always the subject and narrows nothing; two reaches
    the auxiliary, which is where the grammar lives."""
    assert hint_prefix("She doesn't live here.") == "She doesn't"
    assert hint_prefix("Do you speak English?") == "Do you"


def test_the_hint_copes_with_a_sentence_shorter_than_it_wants():
    assert hint_prefix("I work.") == "I work."
    assert hint_prefix("") == ""


def test_the_value_ladder_only_ever_goes_down():
    """Any inversion creates a move worth gaming. The first pass had one: a
    hinted first attempt paid 0.5 against 0.6 for guessing wrong and then
    getting it right, so tapping at random was the paying strategy — and in
    the assisted mode a random tap costs nothing."""
    ladder = [
        credit(1),
        credit(1, hinted=True),
        credit(2),
        credit(2, hinted=True),
        credit(3),
    ]
    assert ladder == sorted(ladder, reverse=True), ladder
    assert len(set(ladder)) == len(ladder), ladder


# ---- topic thresholds ----

from app.domain.constructor import (  # noqa: E402
    MIN_ANSWERS_TO_PASS,
    PASSED,
    STALE,
    TO_TYPING,
    is_stale,
    should_pass,
    should_switch_to_typing,
    update_score,
)


def test_the_thresholds_are_ordered_so_the_stages_cannot_overlap():
    """Magnitudes are a calibration guess; the ordering is not. If passing sat
    below the mode switch a topic could be finished without ever being typed."""
    assert STALE < TO_TYPING < PASSED <= 1.0


def test_tiles_are_dropped_only_once():
    assert should_switch_to_typing(TO_TYPING, typing=False)
    assert not should_switch_to_typing(TO_TYPING - 0.01, typing=False)
    assert not should_switch_to_typing(1.0, typing=True)


def test_a_topic_cannot_be_passed_from_the_assisted_mode():
    """Picking from options cannot prove production — which is the entire
    reason the constructor replaced the gap-fill cards."""
    assert not should_pass(1.0, answered=999, typing=False)
    assert should_pass(1.0, answered=999, typing=True)


def test_a_few_lucky_answers_do_not_pass_a_topic():
    """The decay already forces roughly fifteen clean answers, but leaving that
    implicit means a change to DECAY could quietly let three through."""
    assert not should_pass(1.0, answered=MIN_ANSWERS_TO_PASS - 1, typing=True)


def test_a_clean_run_actually_reaches_passing():
    """A threshold the decay can never reach would leave every topic open
    forever, which is the opposite failure and just as invisible."""
    score = 0.0
    for _ in range(MIN_ANSWERS_TO_PASS * 3):
        score = update_score(score, 1.0)
    assert should_pass(score, answered=MIN_ANSWERS_TO_PASS * 3, typing=True)


def test_going_stale_needs_a_real_slide_not_one_bad_evening():
    """Without the gap between PASSED and STALE the finished list would
    flicker in and out on a single miss."""
    assert not is_stale(PASSED, passed_at_set=True)
    assert not is_stale(STALE + 0.01, passed_at_set=True)
    assert is_stale(STALE - 0.01, passed_at_set=True)


def test_an_unpassed_topic_is_never_stale():
    """Staleness is about decay after finishing; a topic still being learned
    is simply low."""
    assert not is_stale(0.0, passed_at_set=False)
