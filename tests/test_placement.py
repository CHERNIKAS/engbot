from __future__ import annotations

from dataclasses import dataclass

from app.bot.states import InteractionState
from app.domain.enums import LearningTrack
from app.domain.levels import TEST_LEVELS, TEST_PER_LEVEL, TEST_START_LEVEL
from app.services.placement_service import (
    OPTIONS_PER_CARD,
    ORIGIN_ONBOARDING,
    ORIGIN_SETTINGS,
    PlacementService,
    _build_decks,
)


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


async def _run(svc, knows: set[str]) -> tuple[str | None, list[str]]:
    """Take the whole test as someone who can answer exactly `knows`."""
    card = await svc.start(1, LearningTrack.ENGLISH)
    seen: list[str] = []
    verdict = None
    while card is not None:
        level = card.writing[:2].upper()  # fake words are named "a1word0" etc.
        seen.append(level)
        right = level in knows
        chosen = card.correct_index if right else (card.correct_index + 1) % OPTIONS_PER_CARD
        card, verdict = await svc.answer(1, chosen)
    return verdict, seen


# ---- deck building ----


def test_decks_are_grouped_by_level():
    decks = _build_decks({lv: _words(lv) for lv in TEST_LEVELS}, {lv: _pool(lv) for lv in TEST_LEVELS})
    assert set(decks) == set(TEST_LEVELS)
    for level, cards in decks.items():
        assert all(c["level"] == level for c in cards)


def test_every_card_has_the_right_option_count_and_a_valid_answer():
    decks = _build_decks({lv: _words(lv) for lv in TEST_LEVELS}, {lv: _pool(lv) for lv in TEST_LEVELS})
    for cards in decks.values():
        for row in cards:
            assert len(row["options"]) == OPTIONS_PER_CARD
            assert len(set(row["options"])) == OPTIONS_PER_CARD  # no duplicate decoys
            assert 0 <= row["correct"] < OPTIONS_PER_CARD


def test_a_level_that_cannot_fill_its_options_is_dropped():
    assert _build_decks({"A1": _words("A1", 1)}, {"A1": ["вариант_один"]}) == {}


def test_decoy_never_repeats_the_correct_answer():
    word = FakeWord(1, "cat", "кошка")
    decks = _build_decks({"A1": [word]}, {"A1": ["кошка", "КОШКА", "собака", "мышь", "птица"]})
    assert decks["A1"][0]["options"].count("кошка") == 1


def test_word_without_translation_is_skipped():
    assert _build_decks({"A1": [FakeWord(1, "cat", None)]}, {"A1": _pool("A1")}) == {}


# ---- the staircase ----


async def test_the_test_starts_in_the_middle():
    svc = PlacementService(FakeWordRepo(), FakeState())
    card = await svc.start(1, LearningTrack.ENGLISH)
    assert card.writing.startswith(TEST_START_LEVEL.lower())


async def test_a_beginner_is_not_asked_the_hard_levels():
    """Failing early stops the climb — no point showing B2 to someone who
    missed A2."""
    verdict, seen = await _run(PlacementService(FakeWordRepo(), FakeState()), set())
    assert verdict == "A1"
    assert "B1" not in seen and "B2" not in seen


async def test_an_advanced_learner_reaches_the_top():
    verdict, seen = await _run(
        PlacementService(FakeWordRepo(), FakeState()), {"A1", "A2", "B1", "B2"}
    )
    assert verdict == "B2"
    assert set(seen) == {"A2", "B1", "B2"}


async def test_the_staircase_settles_on_the_hardest_level_held():
    verdict, _seen = await _run(PlacementService(FakeWordRepo(), FakeState()), {"A1", "A2", "B1"})
    assert verdict == "B1"


async def test_a_lucky_block_cannot_promote_on_its_own():
    """Reaching B2 requires clearing A2 and B1 first, so guessing one block
    through no longer moves anyone to the top."""
    verdict, _seen = await _run(PlacementService(FakeWordRepo(), FakeState()), {"B2"})
    assert verdict != "B2"


async def test_no_level_is_asked_twice():
    for knows in (set(), {"A1"}, {"A1", "A2"}, {"A1", "A2", "B1"}, {"A1", "A2", "B1", "B2"}):
        _verdict, seen = await _run(PlacementService(FakeWordRepo(), FakeState()), knows)
        blocks = list(dict.fromkeys(seen))
        assert len(blocks) == len(set(blocks)), knows


async def test_the_counter_never_exceeds_the_advertised_maximum():
    svc = PlacementService(FakeWordRepo(), FakeState())
    card = await svc.start(1, LearningTrack.ENGLISH)
    while card is not None:
        assert card.position <= card.total
        card, _verdict = await svc.answer(1, card.correct_index)


# ---- plumbing ----


async def test_start_returns_none_when_catalogue_cannot_fill_a_test():
    svc = PlacementService(FakeWordRepo(words={}, pools={}), FakeState())
    assert await svc.start(1, LearningTrack.ENGLISH) is None


async def test_pool_query_excludes_the_words_being_asked():
    repo = FakeWordRepo()
    await PlacementService(repo, FakeState()).start(1, LearningTrack.ENGLISH)
    for level, excluded in repo.pool_calls:
        assert excluded == [w.id for w in repo._words[level][:TEST_PER_LEVEL]]


async def test_answer_outside_the_test_state_is_ignored():
    svc = PlacementService(FakeWordRepo(), FakeState())
    assert await svc.answer(1, 0) == (None, None)


async def test_origin_defaults_to_onboarding():
    svc = PlacementService(FakeWordRepo(), FakeState())
    await svc.start(1, LearningTrack.ENGLISH)
    assert await svc.origin_of(1) == ORIGIN_ONBOARDING


async def test_origin_survives_every_answer():
    """It's read only at the end, so it has to ride the whole test."""
    svc = PlacementService(FakeWordRepo(), FakeState())
    card = await svc.start(1, LearningTrack.ENGLISH, origin=ORIGIN_SETTINGS)
    while card is not None:
        assert await svc.origin_of(1) == ORIGIN_SETTINGS
        card, _verdict = await svc.answer(1, card.correct_index)
