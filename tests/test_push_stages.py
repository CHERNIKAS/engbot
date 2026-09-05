"""Production ladder: the card type is derived from the word's reps against that
word's own mastery bar. The bar depends on how far the word sits from the user's
level, and the rungs scale with it (levels.ladder_stages), so these tests pin a
word two levels above the user — bar 10, rungs 3 and 5 — to cover the classic
shape, plus a set at a shorter bar. New → recognition; a miss drops down the
ladder; mastered rotate."""
from __future__ import annotations

from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import (
    CARD_CLOZE,
    CARD_RECOGNITION,
    CARD_REVERSE,
    CARD_TYPE_IN,
    PushService,
)


def _svc() -> PushService:
    return PushService(session=None, redis=None, bot=None)  # type: ignore[arg-type]


def _uw(status: str, reps: int):
    return SimpleNamespace(status=status, repetitions_count=reps)


# gap(+2) from USER_LEVEL -> the legacy bar of 10, rungs at 3 and 5.
USER_LEVEL = "A2"
FAR_LEVEL = "B2"


def _word(
    example: str | None = "She teaches English daily.",
    writing: str = "teach",
    level: str | None = FAR_LEVEL,
):
    return SimpleNamespace(example_sentence=example, writing=writing, level=level)


def test_new_word_is_recognition_regardless_of_reps():
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.NEW.value, 0), _word(), USER_LEVEL) == CARD_RECOGNITION
    assert svc._card_type(_uw(WordStatus.NEW.value, 9), _word(), USER_LEVEL) == CARD_RECOGNITION


def test_stage_zero_is_recognition():
    svc = _svc()
    for reps in (0, 1, 2):
        assert svc._card_type(_uw(WordStatus.LEARNING.value, reps), _word(), USER_LEVEL) == CARD_RECOGNITION


def test_reverse_rung_is_reps_3_and_4():
    svc = _svc()
    for reps in (3, 4):
        assert svc._card_type(_uw(WordStatus.REVIEW.value, reps), _word(), USER_LEVEL) == CARD_REVERSE


def test_typing_rung_is_reps_5_through_9():
    svc = _svc()
    for reps in (5, 6, 7, 8, 9):
        assert svc._card_type(_uw(WordStatus.REVIEW.value, reps), _word(), USER_LEVEL) == CARD_CLOZE


def test_typing_rung_types_the_whole_word_when_not_maskable():
    """Irregular form (no maskable example) → still the typing rung: write the
    word out in full instead of filling a blank. Falling back to reverse here
    meant a phrase like «Is it far from here?» was never once produced."""
    svc = _svc()
    w = _word(example="She went home.", writing="go")  # 'go' not literally present
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 6), w, USER_LEVEL) == CARD_TYPE_IN


def test_typing_rung_types_it_out_when_there_is_no_example():
    svc = _svc()
    w = _word(example=None)
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 5), w, USER_LEVEL) == CARD_TYPE_IN


def test_miss_drops_back_to_recognition():
    """Lapses walk reps back down → low reps land on recognition again."""
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.LEARNING.value, 0), _word(), USER_LEVEL) == CARD_RECOGNITION


def test_mastered_rotates_among_valid_types():
    svc = _svc()
    seen = set()
    for _ in range(60):
        seen.add(svc._card_type(_uw(WordStatus.MASTERED.value, 12), _word(), USER_LEVEL))
    assert seen <= {CARD_RECOGNITION, CARD_REVERSE, CARD_CLOZE}
    assert len(seen) >= 2  # genuinely rotating


def test_mastered_without_cloze_only_recognition_or_reverse():
    svc = _svc()
    w = _word(example=None)
    for _ in range(40):
        assert svc._card_type(_uw(WordStatus.MASTERED.value, 12), w, USER_LEVEL) in {CARD_RECOGNITION, CARD_REVERSE}


# ---- the ladder scales with the word's own bar ----


def test_easier_word_still_walks_all_three_rungs():
    """A word at the user's level masters at 6, not 10. The rungs have to
    compress with it — pinning them to 3/5 would leave a single typed rep."""
    svc = _svc()
    at_level = _word(level=USER_LEVEL)
    types = [
        svc._card_type(_uw(WordStatus.REVIEW.value, reps), at_level, USER_LEVEL)
        for reps in range(6)
    ]
    assert types[0] == CARD_RECOGNITION
    assert CARD_REVERSE in types
    assert CARD_CLOZE in types


def test_far_below_level_word_is_never_promoted_before_being_typed():
    """Even at the shortest bar the user must produce the word at least once."""
    svc = _svc()
    easy = _word(level="A1")
    types = [
        svc._card_type(_uw(WordStatus.REVIEW.value, reps), easy, "B1") for reps in range(3)
    ]
    assert CARD_CLOZE in types


def test_same_word_climbs_later_for_a_weaker_user():
    """The word is fixed; only the user's level differs. The one for whom it is
    a stretch should still be on choice cards where the stronger user types."""
    svc = _svc()
    w = _word(level="B2")
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 3), w, "B2") == CARD_CLOZE
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 3), w, "A1") != CARD_CLOZE


# ---- phrases: the top rung when a blank is impossible ----


def test_a_phrase_reaches_production_by_being_written_out():
    """106 phrasebook entries can never take a cloze — a whole sentence has no
    single word to mask. Before this rung they graduated on recognition alone."""
    svc = _svc()
    phrase = _word(example=None, writing="Is it far from here?")
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 9), phrase, USER_LEVEL) == CARD_TYPE_IN


def test_a_maskable_word_still_prefers_the_blank():
    """Type-in is the fallback, not a replacement: a sentence with context left
    is the better card, so cloze wins whenever it is possible."""
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 9), _word(), USER_LEVEL) == CARD_CLOZE
