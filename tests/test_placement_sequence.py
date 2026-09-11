"""The placement test asks the questions it claims to ask, in order.

Mutation testing found the sequencing untested: advancing two cards at a
time (so a level was judged on two answers instead of three), skipping the
first card of every new level, and a card numbered 0 all passed the suite.
These drive the real start/answer loop and check what the learner sees.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.bot.states import InteractionState
from app.domain.enums import LearningTrack
from app.domain.levels import TEST_LEVELS, TEST_PER_LEVEL
from app.services.placement_service import OPTIONS_PER_CARD, PlacementService


@dataclass
class _Word:
    id: int
    writing: str
    translation: str


class _Repo:
    def __init__(self, levels=TEST_LEVELS):
        self._levels = set(levels)

    async def pick_placement_words(self, track, levels, per_level):
        out = {}
        for lv in levels:
            if lv in self._levels:
                base = TEST_LEVELS.index(lv) * 100
                out[lv] = [
                    _Word(base + i, f"{lv.lower()}word{i}", f"perevod{base + i}")
                    for i in range(per_level)
                ]
        return out

    async def placement_translations(self, track, level, exclude_ids, limit):
        base = TEST_LEVELS.index(level) * 100
        return [f"variant{base}_{i}" for i in range(20)][:limit]


class _State:
    def __init__(self):
        self.state = InteractionState.IDLE
        self.data: dict = {}

    async def set(self, user_id, state, data=None, ttl=None):
        self.state, self.data = state, dict(data or {})

    async def get(self, user_id):
        from app.services.interaction_state_service import StatePayload

        return StatePayload(state=self.state, data=dict(self.data))


async def _take(svc, knows_all: bool = True):
    """Run the whole test; return every card shown and the verdict."""
    cards = []
    card = await svc.start(1, LearningTrack.ENGLISH)
    verdict = None
    while card is not None:
        cards.append(card)
        wrong = (card.correct_index + 1) % OPTIONS_PER_CARD
        card, verdict = await svc.answer(1, card.correct_index if knows_all else wrong)
    return cards, verdict


async def test_every_level_asks_exactly_its_block_and_starts_at_the_first_word():
    cards, verdict = await _take(PlacementService(_Repo(), _State()))
    by_level: dict[str, list[str]] = {}
    for c in cards:
        by_level.setdefault(c.writing[:2].upper(), []).append(c.writing)
    assert verdict == TEST_LEVELS[-1]
    for level, words in by_level.items():
        assert len(words) == TEST_PER_LEVEL, (level, words)
        assert len(set(words)) == TEST_PER_LEVEL, (level, words)
        assert f"{level.lower()}word0" in words, (level, words)


async def test_questions_are_numbered_one_by_one_across_levels():
    cards, _ = await _take(PlacementService(_Repo(), _State()))
    assert [c.position for c in cards] == list(range(1, len(cards) + 1))


async def test_a_level_with_no_words_ends_the_test_instead_of_crashing():
    """The next level up has nothing to ask: settle on what is held."""
    repo = _Repo(levels=[lv for lv in TEST_LEVELS if lv != "B1"])
    cards, verdict = await _take(PlacementService(repo, _State()))
    assert verdict == "A2"
    assert all(c.writing[:2].upper() != "B1" for c in cards)


async def test_an_answer_after_the_last_card_is_ignored_not_a_crash():
    state = _State()
    svc = PlacementService(_Repo(), state)
    await svc.start(1, LearningTrack.ENGLISH)
    level = state.data["level"]
    state.data["pos"] = len(state.data["decks"][level])
    assert await svc.answer(1, 0) == (None, None)
