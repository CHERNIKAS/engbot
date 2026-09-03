from __future__ import annotations

from dataclasses import dataclass

from app.bot.states import InteractionState
from app.domain.enums import LearningTrack
from app.domain.levels import TEST_LEVELS, TEST_PER_LEVEL
from app.services.placement_service import OPTIONS_PER_CARD, PlacementService, _build_deck


@dataclass
class FakeWord:
    id: int
    writing: str
    translation: str | None


def _words(level: str, n: int = TEST_PER_LEVEL) -> list[FakeWord]:
    base = TEST_LEVELS.index(level) * 100
    return [FakeWord(base + i, f"{level.lower()}word{i}", f"перевод{base + i}") for i in range(n)]


def _pool(level: str, n: int = 20) -> list[str]:
    base = TEST_LEVELS.index(level) * 100
    return [f"вариант{base}_{i}" for i in range(n)]


class FakeWordRepo:
    def __init__(self, words=None, pools=None):
        self._words = words if words is not None else {lv: _words(lv) for lv in TEST_LEVELS}
        self._pools = pools if pools is not None else {lv: _pool(lv) for lv in TEST_LEVELS}
        self.pool_calls: list[tuple[str, list[int]]] = []

    async def pick_placement_words(self, track, levels, per_level):
        return {lv: self._words[lv][:per_level] for lv in levels if self._words.get(lv)}

    async def placement_translations(self, track, level, exclude_ids, limit):
        self.pool_calls.append((level, list(exclude_ids)))
        return self._pools.get(level, [])[:limit]


class FakeState:
    def __init__(self):
        self.state = InteractionState.IDLE
        self.data: dict = {}

    async def set(self, user_id, state, data=None, ttl=None):
        self.state, self.data = state, dict(data or {})

    async def get(self, user_id):
        from app.services.interaction_state_service import StatePayload

        return StatePayload(state=self.state, data=dict(self.data))


# ---- deck building ----


def test_deck_is_ordered_easiest_level_first():
    deck = _build_deck({lv: _words(lv) for lv in TEST_LEVELS}, {lv: _pool(lv) for lv in TEST_LEVELS})
    assert [row["level"] for row in deck[:TEST_PER_LEVEL]] == [TEST_LEVELS[0]] * TEST_PER_LEVEL
    seen_order = list(dict.fromkeys(row["level"] for row in deck))
    assert seen_order == list(TEST_LEVELS)


def test_every_card_has_the_right_option_count_and_a_valid_answer():
    deck = _build_deck({lv: _words(lv) for lv in TEST_LEVELS}, {lv: _pool(lv) for lv in TEST_LEVELS})
    for row in deck:
        assert len(row["options"]) == OPTIONS_PER_CARD
        assert len(set(row["options"])) == OPTIONS_PER_CARD  # no duplicate decoys
        assert 0 <= row["correct"] < OPTIONS_PER_CARD


def test_card_is_dropped_when_its_level_cannot_fill_the_options():
    # Only one usable decoy for A1 — that card can't be built fairly.
    deck = _build_deck({"A1": _words("A1", 1)}, {"A1": ["вариант_один"]})
    assert deck == []


def test_decoy_never_repeats_the_correct_answer():
    word = FakeWord(1, "cat", "кошка")
    deck = _build_deck({"A1": [word]}, {"A1": ["кошка", "КОШКА", "собака", "мышь", "птица"]})
    assert len(deck) == 1
    assert deck[0]["options"].count("кошка") == 1


def test_word_without_translation_is_skipped():
    deck = _build_deck({"A1": [FakeWord(1, "cat", None)]}, {"A1": _pool("A1")})
    assert deck == []


# ---- running the test ----


async def test_start_stores_state_and_returns_first_card():
    state = FakeState()
    svc = PlacementService(FakeWordRepo(), state)
    card = await svc.start(1, LearningTrack.ENGLISH)
    assert card is not None
    assert card.position == 1
    assert card.total == len(TEST_LEVELS) * TEST_PER_LEVEL
    assert state.state == InteractionState.ONBOARDING_LEVEL
    assert state.data["pos"] == 0


async def test_start_returns_none_when_catalogue_cannot_fill_a_test():
    svc = PlacementService(FakeWordRepo(words={}, pools={}), FakeState())
    assert await svc.start(1, LearningTrack.ENGLISH) is None


async def test_pool_query_excludes_the_words_being_asked():
    repo = FakeWordRepo()
    await PlacementService(repo, FakeState()).start(1, LearningTrack.ENGLISH)
    for level, excluded in repo.pool_calls:
        assert excluded == [w.id for w in repo._words[level][:TEST_PER_LEVEL]]


async def test_answering_everything_right_reaches_the_top_tested_level():
    state = FakeState()
    svc = PlacementService(FakeWordRepo(), state)
    card = await svc.start(1, LearningTrack.ENGLISH)
    verdict = None
    while card is not None:
        card, verdict = await svc.answer(1, card.correct_index)
    assert verdict == TEST_LEVELS[-1]


async def test_failing_from_the_start_floors_at_a1():
    state = FakeState()
    svc = PlacementService(FakeWordRepo(), state)
    card = await svc.start(1, LearningTrack.ENGLISH)
    verdict = None
    while card is not None:
        wrong = (card.correct_index + 1) % OPTIONS_PER_CARD
        card, verdict = await svc.answer(1, wrong)
    assert verdict == "A1"


async def test_position_counter_advances():
    state = FakeState()
    svc = PlacementService(FakeWordRepo(), state)
    card = await svc.start(1, LearningTrack.ENGLISH)
    assert card.position == 1
    card, _ = await svc.answer(1, card.correct_index)
    assert card.position == 2


async def test_answer_outside_the_test_state_is_ignored():
    svc = PlacementService(FakeWordRepo(), FakeState())
    assert await svc.answer(1, 0) == (None, None)
