"""Production ladder: the card type is derived from the word's stage
(consecutive-correct // STAGE_STEP). New → recognition; a miss (reps=0) drops
back to recognition; mastered words rotate types."""
from __future__ import annotations

import random
from types import SimpleNamespace

from app.domain.enums import WordStatus
from app.services.push_service import (
    CARD_CLOZE,
    CARD_RECOGNITION,
    CARD_REVERSE,
    PushService,
)


def _svc() -> PushService:
    return PushService(session=None, redis=None, bot=None)  # type: ignore[arg-type]


def _uw(status: str, reps: int):
    return SimpleNamespace(status=status, repetitions_count=reps)


def _word(example: str | None = "She teaches English daily.", writing: str = "teach"):
    return SimpleNamespace(example_sentence=example, writing=writing)


def test_new_word_is_recognition_regardless_of_reps():
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.NEW.value, 0), _word()) == CARD_RECOGNITION
    assert svc._card_type(_uw(WordStatus.NEW.value, 9), _word()) == CARD_RECOGNITION


def test_stage_zero_is_recognition():
    svc = _svc()
    for reps in (0, 1, 2):
        assert svc._card_type(_uw(WordStatus.LEARNING.value, reps), _word()) == CARD_RECOGNITION


def test_stage_one_is_reverse():
    svc = _svc()
    for reps in (3, 4, 5):
        assert svc._card_type(_uw(WordStatus.REVIEW.value, reps), _word()) == CARD_REVERSE


def test_stage_two_is_cloze_when_maskable():
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 6), _word()) == CARD_CLOZE
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 9), _word()) == CARD_CLOZE


def test_stage_two_falls_back_to_reverse_when_not_maskable():
    """Irregular form (no maskable example) → stage 2 shows reverse, not cloze."""
    svc = _svc()
    w = _word(example="She went home.", writing="go")  # 'go' not literally present
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 6), w) == CARD_REVERSE


def test_stage_two_falls_back_when_no_example():
    svc = _svc()
    w = _word(example=None)
    assert svc._card_type(_uw(WordStatus.REVIEW.value, 6), w) == CARD_REVERSE


def test_miss_drops_back_to_recognition():
    """A wrong answer zeroes reps → stage 0 → recognition (gentle restart)."""
    svc = _svc()
    assert svc._card_type(_uw(WordStatus.LEARNING.value, 0), _word()) == CARD_RECOGNITION


def test_mastered_rotates_among_valid_types():
    svc = _svc()
    seen = set()
    for _ in range(60):
        seen.add(svc._card_type(_uw(WordStatus.MASTERED.value, 12), _word()))
    assert seen <= {CARD_RECOGNITION, CARD_REVERSE, CARD_CLOZE}
    assert len(seen) >= 2  # genuinely rotating


def test_mastered_without_cloze_only_recognition_or_reverse():
    svc = _svc()
    w = _word(example=None)
    for _ in range(40):
        assert svc._card_type(_uw(WordStatus.MASTERED.value, 12), w) in {CARD_RECOGNITION, CARD_REVERSE}
