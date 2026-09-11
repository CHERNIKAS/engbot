"""Property-based tests: invariants that must hold for ANY input, not the
handful of examples a person thinks of. Each one guards a class of bug this
codebase has actually shipped (overflow on long review chains, a pool that
converged onto its own ceiling, a picker serving words that weren't due, a
"learned" bar that was hardest for the easiest words).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.domain import levels, mastery, pacing
from app.domain.enums import LearningPace, ReviewResult, WordStatus
from app.domain.push import in_window, normalize_window, window_hours
from app.domain.study_drill import is_typing_correct
from app.services.push_service import (
    _in_days_phrase,
    _looks_like_typed_answer,
    _mask_target,
    _percent,
)
from app.services.repetition_service import (
    MASTERY_SCORE_MAX,
    MAX_INTERVAL_DAYS,
    apply_review,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
LEVEL = st.sampled_from(levels.LEVELS)
MAYBE_LEVEL = st.one_of(st.none(), LEVEL)


def _by_difficulty(a, b):
    return sorted((a, b), key=levels.index)


# ---- push window ----------------------------------------------------------


@given(st.integers(0, 23), st.integers(1, 24))
def test_the_window_length_is_exactly_the_hours_it_admits(start, end):
    """Two functions describe one window; they must never disagree about it."""
    admitted = sum(in_window(h, start, end) for h in range(24))
    assert admitted == window_hours(start, end)


@given(st.integers(-5, 30), st.integers(-5, 30), st.integers(1, 23))
def test_normalize_returns_the_input_only_when_it_is_valid(start, end, min_hours):
    default = (10, 22)
    out = normalize_window(start, end, min_hours=min_hours, default=default)
    if out != default:
        assert out == (start, end)
        assert min_hours <= window_hours(start, end) < 24


# ---- pool sizing and the backlog offer ------------------------------------


@given(st.one_of(st.none(), st.floats(-10, 1000, allow_nan=False)))
def test_the_pool_ceiling_stays_in_bounds(rate):
    assert pacing.MIN_POOL <= pacing.pool_ceiling(rate) <= pacing.MAX_POOL


@given(st.floats(0, 500, allow_nan=False), st.floats(0, 500, allow_nan=False))
def test_answering_more_never_shrinks_the_pool(a, b):
    lo, hi = sorted((a, b))
    assume(lo > 0)
    assert pacing.pool_ceiling(lo) <= pacing.pool_ceiling(hi)


@given(st.integers(0, 400), st.floats(0.1, 200, allow_nan=False))
def test_an_offer_never_takes_more_than_half_or_below_the_target(active, rate):
    ceiling = pacing.pool_ceiling(rate)
    n = pacing.overflow(active, ceiling)
    assert 0 <= n <= int(active * pacing.MAX_OFFER_SHARE)
    target = max(pacing.MIN_POOL, round(ceiling * pacing.POOL_TARGET_SHARE))
    assert n <= max(0, active - target)


@given(st.integers(0, 400), st.floats(0.1, 200, allow_nan=False))
def test_accepting_offers_always_reopens_intake(active, rate):
    """New words enter only while the pool is strictly under the ceiling. If
    repeatedly accepting the offer can stall at or above it, the user parks
    words and still never gets anything new -- shipped once already.

    Excludes a ceiling sitting on the MIN_POOL floor: there the target equals
    the ceiling by construction, the pool is minimal rather than oversized, and
    the way out is graduating a word, not parking one of five.
    """
    ceiling = pacing.pool_ceiling(rate)
    assume(ceiling > pacing.MIN_POOL)
    for _ in range(50):
        if active < ceiling:
            break
        n = pacing.overflow(active, ceiling)
        assert n > 0, f"stuck at {active} with ceiling {ceiling}"
        active -= n
    assert active < ceiling


# ---- levels and the placement staircase -----------------------------------


@given(st.lists(st.booleans(), min_size=len(levels.TEST_LEVELS), max_size=len(levels.TEST_LEVELS)))
def test_the_staircase_always_ends_with_a_real_level(outcomes):
    current, tested, verdict = levels.TEST_START_LEVEL, set(), None
    for passed in outcomes:
        tested.add(current)
        nxt, verdict = levels.next_test_level(current, passed, tested)
        if nxt is None:
            break
        assert nxt not in tested, "the staircase revisited a level"
        current = nxt
    else:
        raise AssertionError("the staircase did not stop")
    assert verdict in levels.TEST_LEVELS


def test_passing_everything_reaches_the_top_and_failing_everything_the_floor():
    for passed, expected in ((True, levels.TEST_LEVELS[-1]), (False, levels.TEST_LEVELS[0])):
        current, tested = levels.TEST_START_LEVEL, set()
        while True:
            tested.add(current)
            nxt, verdict = levels.next_test_level(current, passed, tested)
            if nxt is None:
                break
            current = nxt
        assert verdict == expected


@given(MAYBE_LEVEL, MAYBE_LEVEL)
def test_gap_is_antisymmetric(a, b):
    assert levels.gap(a, b) == -levels.gap(b, a)


@given(MAYBE_LEVEL, st.integers(-10, 10))
def test_shift_stays_on_the_scale(level, steps):
    assert levels.shift(level, steps) in levels.LEVELS


@given(MAYBE_LEVEL, MAYBE_LEVEL)
def test_every_word_walks_every_rung_before_it_can_graduate(word_level, user_level):
    """Recognition, then reverse, then typing -- each for at least one rep,
    all before the bar. A rung that collapses lets a word skip being typed."""
    bar = levels.mastery_reps(word_level, user_level)
    reverse_at, typing_at = levels.ladder_stages(bar)
    assert 1 <= reverse_at < typing_at < bar


@given(LEVEL, LEVEL, LEVEL)
def test_a_harder_word_never_needs_fewer_reps(user, a, b):
    """Found by this suite: gap -3 missed the table and fell to the bar for
    words far ABOVE the user, so an A1 word for a B2 learner needed the most."""
    easy, hard = _by_difficulty(a, b)
    assert levels.mastery_reps(easy, user) <= levels.mastery_reps(hard, user)


# ---- what "learned" means -------------------------------------------------


KINDS = st.sampled_from([
    mastery.RECOGNITION, mastery.REVERSE, mastery.TYPED_EXACT, mastery.TYPED_TYPO,
    mastery.TYPED_SYNONYM, mastery.TYPED_GRAMMAR, mastery.WRONG,
])


@given(st.floats(0, 30, allow_nan=False), st.integers(0, 20), MAYBE_LEVEL, MAYBE_LEVEL, st.booleans())
def test_more_score_or_more_typing_never_unlearns_a_word(score, typed, wl, ul, possible):
    if mastery.is_mastered(score, typed, wl, ul, production_possible=possible):
        assert mastery.is_mastered(score + 1.0, typed, wl, ul, production_possible=possible)
        assert mastery.is_mastered(score, typed + 1, wl, ul, production_possible=possible)


@given(st.floats(0, 100, allow_nan=False), MAYBE_LEVEL, MAYBE_LEVEL)
def test_no_score_graduates_a_word_that_was_never_typed(score, wl, ul):
    """The production floor: guessable cards alone can't make a word learned."""
    assert not mastery.is_mastered(score, 0, wl, ul, production_possible=True)


@given(LEVEL, LEVEL, LEVEL)
def test_a_harder_word_never_has_a_lower_bar(user, a, b):
    """Found by this suite: user B2, an A2 word needed 5.5 and an A1 word 12.5
    -- the hardest bar in the table, for the easiest words the user has."""
    easy, hard = _by_difficulty(a, b)
    easy_bar, hard_bar = mastery.target_for(easy, user), mastery.target_for(hard, user)
    assert easy_bar[0] <= hard_bar[0]
    assert easy_bar[1] <= hard_bar[1]


@given(st.floats(0, 50, allow_nan=False), KINDS)
def test_only_a_wrong_answer_lowers_the_score(score, kind):
    after = mastery.apply_credit(score, kind)
    assert after >= 0.0
    if kind == mastery.WRONG:
        assert after <= score
    else:
        assert after > score


# ---- the scheduler ---------------------------------------------------------


RESULTS = st.sampled_from([
    ReviewResult.CORRECT, ReviewResult.WRONG, ReviewResult.NORMAL, ReviewResult.HARD, ReviewResult.EASY,
])


def _uw(status):
    return SimpleNamespace(
        status=status, ease_score=2.5, repetitions_count=0, mistakes_count=0,
        interval_days=0.0, learning_score=0.0, production_count=0, mastery_score=5.0,
        last_reviewed_at=None, next_review_at=NOW,
    )


@settings(max_examples=200)
@given(
    st.sampled_from([WordStatus.NEW.value, WordStatus.LEARNING.value, WordStatus.MASTERED.value]),
    st.lists(st.tuples(RESULTS, st.one_of(st.none(), KINDS)), min_size=1, max_size=120),
    st.sampled_from(list(LearningPace)),
    MAYBE_LEVEL,
    MAYBE_LEVEL,
)
def test_any_review_history_keeps_the_schedule_sane(status, history, pace, wl, ul):
    """Long chains once compounded the interval into OverflowError. Whatever
    the history: no crash, the next review is never in the past, intervals and
    scores stay in range, and a learned word stays learned."""
    uw = _uw(status)
    now = NOW
    was_mastered = False
    for result, kind in history:
        apply_review(uw, result, pace, now=now, kind=kind, word_level=wl, user_level=ul)
        assert uw.next_review_at >= now
        assert 0 < uw.interval_days <= MAX_INTERVAL_DAYS
        assert 0.0 <= (uw.mastery_score or 0.0) <= MASTERY_SCORE_MAX
        assert (uw.learning_score or 0.0) >= 0.0
        if was_mastered:
            assert uw.status == WordStatus.MASTERED.value
        was_mastered = uw.status == WordStatus.MASTERED.value
        now = uw.next_review_at


@given(st.lists(RESULTS, min_size=1, max_size=40), st.sampled_from(list(LearningPace)))
def test_every_review_of_a_learned_word_reschedules_it(history, pace):
    """The bug just fixed: a mastered word's review left next_review_at alone,
    so a word that came due stayed due forever."""
    uw = _uw(WordStatus.MASTERED.value)
    uw.next_review_at = NOW - timedelta(days=60)
    now = NOW
    for result in history:
        apply_review(uw, result, pace, now=now)
        assert uw.next_review_at >= now + timedelta(hours=20)
        now = uw.next_review_at


# ---- typed answers ---------------------------------------------------------


WORD = st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=15)
SEPARATORS = st.sampled_from(["|", " - ", " — ", " – ", "\t", "\n"])
CYRILLIC = st.characters(min_codepoint=0x0430, max_codepoint=0x044F)
WITH_CYRILLIC = st.tuples(st.text(max_size=20), CYRILLIC, st.text(max_size=20)).map("".join)


@given(WORD)
def test_the_right_word_is_always_accepted(w):
    assert is_typing_correct(w, w)
    assert is_typing_correct(f"  {w.upper()}  ", w)


@given(WORD, WORD)
def test_a_short_word_needs_an_exact_match(a, b):
    assume(len(b) < 4 and a != b)
    assert not is_typing_correct(a, b)


@given(WITH_CYRILLIC)
def test_cyrillic_is_never_taken_as_an_answer(text):
    for card in ("cloze", "type_in"):
        assert not _looks_like_typed_answer(text, card)


@given(WORD, SEPARATORS, WORD)
def test_a_quick_add_is_never_taken_as_an_answer(a, sep, b):
    for card in ("cloze", "type_in"):
        assert not _looks_like_typed_answer(f"{a}{sep}{b}", card)


@given(WORD, WORD, WORD)
def test_a_masked_sentence_never_leaks_the_answer(before, target, after):
    assume(len(target) >= 2 and target not in before and target not in after)
    sentence = f"{before.capitalize()} {target} {after}."
    masked = _mask_target(sentence, target)
    assert masked is not None
    assert "___" in masked
    assert f" {target} " not in f" {masked.lower()} "


# ---- recap helpers ---------------------------------------------------------


@given(st.floats(0, 100, allow_nan=False), st.floats(0.5, 20, allow_nan=False))
def test_progress_percent_stays_in_range(score, bar):
    """Scores are floored at zero by apply_credit (and prod holds no negative
    ones), so the range to cover starts there."""
    uw = SimpleNamespace(learning_score=score)
    assert 0 <= _percent(uw, (bar, 0)) <= 100


@given(st.integers(-400, 400))
def test_every_due_date_has_a_phrase(days):
    assert _in_days_phrase(NOW + timedelta(days=days), NOW)
