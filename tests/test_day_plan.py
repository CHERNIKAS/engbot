"""How a day is composed, pinned as behaviour rather than as numbers.

The plan replaces a weighted lottery that no one could predict or finish. These
cover the cases that made the lottery fail: a first day with nothing to repeat,
a return from a long absence with everything overdue, and a catalogue that
cannot supply what the plan asks for.
"""
from __future__ import annotations

from app.domain.day_plan import (
    DEFAULT_SIZE,
    TRIAGE,
    TRIAGE_THRESHOLD,
    GRAMMAR_PER_DAY,
    MAX_NEW_WORDS,
    MAX_SIZE,
    MIN_NEW_WORDS,
    MIN_SIZE,
    PHRASES_PER_DAY,
    compose,
    is_closed,
    next_size,
    remaining_percent,
)

PLENTY = 10_000


def _full(size=DEFAULT_SIZE, due=0, grammar=PLENTY, phrases=PLENTY, new=PLENTY):
    return compose(size, due, grammar, phrases, new)


def test_day_one_is_small_because_there_is_nothing_to_repeat():
    """Filling 28 slots on day one would mean 24 new words in one evening, and
    nothing about ~8 touches per word survives that."""
    c = _full(due=0)
    assert c.repeats == 0
    assert c.new_words == MAX_NEW_WORDS
    assert c.total == MAX_NEW_WORDS + GRAMMAR_PER_DAY + PHRASES_PER_DAY
    assert c.total < DEFAULT_SIZE


def test_the_plan_reaches_its_size_once_review_load_arrives():
    c = _full(due=100)
    assert c.total == DEFAULT_SIZE


def test_repeats_never_squeeze_out_new_words():
    """A returning learner has everything overdue at once. If repeats took the
    whole plan there would be days — weeks — with nothing new, which is the
    fastest way to make catching up feel like punishment."""
    c = _full(due=PLENTY)
    assert c.new_words >= MIN_NEW_WORDS
    assert c.grammar == GRAMMAR_PER_DAY
    assert c.phrases == PHRASES_PER_DAY


def test_grammar_and_phrases_are_never_crowded_out():
    """Review load grows without limit; these do not. Without a fixed share
    they would vanish from the day within a month."""
    for due in (0, 5, 50, PLENTY):
        c = _full(due=due)
        assert c.grammar == GRAMMAR_PER_DAY, due
        assert c.phrases == PHRASES_PER_DAY, due


def test_every_day_carries_at_least_one_theme_word():
    """Corpus rank alone spends a beginner's first month on `organization` and
    `performance` — it ranks written English and has no `apple` at all."""
    for due in (0, 20, PLENTY):
        c = _full(due=due)
        assert c.new_theme >= 1, due
        assert c.new_frequency >= c.new_theme, due


def test_the_plan_never_asks_for_cards_that_do_not_exist():
    """An unsatisfiable plan can never be closed, and an unclosed plan blocks
    every day after it."""
    c = compose(DEFAULT_SIZE, due_repeats=2, grammar_available=1, phrases_available=0, new_available=4)
    assert c.repeats == 2
    assert c.grammar == 1
    assert c.phrases == 0
    assert c.new_words == 4
    assert c.total == 7


def test_an_empty_catalogue_yields_an_empty_plan_not_a_broken_one():
    c = compose(DEFAULT_SIZE, 0, 0, 0, 0)
    assert c.total == 0
    assert is_closed(0, c.total)


def test_size_is_clamped_however_it_is_called():
    assert compose(1000, PLENTY, PLENTY, PLENTY, PLENTY).total == MAX_SIZE
    assert compose(1, PLENTY, PLENTY, PLENTY, PLENTY).total == MIN_SIZE


def test_growth_needs_a_week_and_shrinking_needs_three_days():
    """Asymmetric on purpose: too big is what makes someone quit, too small
    only costs a little progress."""
    assert next_size(28, consecutive_closes=6, consecutive_misses=0) == 28
    assert next_size(28, consecutive_closes=7, consecutive_misses=0) == 30
    assert next_size(28, consecutive_closes=0, consecutive_misses=2) == 28
    assert next_size(28, consecutive_closes=0, consecutive_misses=3) == 26


def test_shrinking_wins_when_both_streaks_somehow_apply():
    assert next_size(28, consecutive_closes=99, consecutive_misses=99) == 26


def test_resizing_respects_the_bounds():
    assert next_size(MAX_SIZE, consecutive_closes=99, consecutive_misses=0) == MAX_SIZE
    assert next_size(MIN_SIZE, consecutive_closes=0, consecutive_misses=99) == MIN_SIZE


def test_one_unanswered_card_never_reports_as_nothing_left():
    """«осталось добить 0%» on an open plan reads as a bug."""
    assert remaining_percent(39, 40) == 2
    assert remaining_percent(199, 200) == 1  # rounds to 0, floored to 1
    assert remaining_percent(0, 28) == 100
    assert remaining_percent(28, 28) == 0
    assert remaining_percent(0, 0) == 0


def test_a_full_batch_of_known_words_books_a_triage_slot():
    """The triage screen is the only slot that makes the rest of the day
    smaller, and it was never reachable: `_items_for` built five kinds and
    neither triage nor the topic test was among them. The learner's recourse was
    the «я это знаю» button, one card at a time, on words like «one» and
    «fourteen»."""
    c = compose(
        size=28, due_repeats=5, grammar_available=4, phrases_available=2,
        new_available=10, triage_available=TRIAGE_THRESHOLD,
    )
    assert c.triage == 1
    assert TRIAGE in [i["kind"] for i in _items(c)]


def test_a_short_batch_does_not_book_one():
    """Fewer than a screenful is what the card button is for; spending a slot
    there costs a card and clears a handful."""
    c = compose(
        size=28, due_repeats=5, grammar_available=4, phrases_available=2,
        new_available=10, triage_available=TRIAGE_THRESHOLD - 1,
    )
    assert c.triage == 0


def test_a_due_topic_books_exactly_one_test():
    c = compose(
        size=28, due_repeats=5, grammar_available=4, phrases_available=2,
        new_available=10, test_due=True,
    )
    assert c.test == 1


def test_the_two_offers_yield_to_the_new_words_on_a_small_day():
    """Booked ahead of the floor they produced a day of four grammar cards, a
    screen, a test and nothing new to learn. They are taken out of what is left
    after grammar, phrases and the new words, so the smallest day still teaches."""
    small = compose(
        size=MIN_SIZE, due_repeats=99, grammar_available=4,
        phrases_available=2, new_available=10,
        triage_available=TRIAGE_THRESHOLD, test_due=True,
    )
    assert (small.triage, small.test) == (0, 0)
    assert small.new_words > 0
    assert small.total <= MIN_SIZE

    roomy = compose(
        size=DEFAULT_SIZE, due_repeats=99, grammar_available=4,
        phrases_available=2, new_available=10,
        triage_available=TRIAGE_THRESHOLD, test_due=True,
    )
    assert (roomy.triage, roomy.test) == (1, 1)
    assert roomy.new_words >= MIN_NEW_WORDS
    assert roomy.total <= DEFAULT_SIZE


def _items(c):
    from app.services.day_plan_service import DayPlanService

    return DayPlanService._items_for(c)
