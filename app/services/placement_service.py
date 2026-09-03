"""The onboarding placement test: a short quiz that gives `users.level` a value.

Kept out of the handlers because the interesting parts — building the card deck
and turning answers into a level — are testable on their own; the handler only
renders whatever card this service hands back.

A recognition quiz rather than "pick your level" or "do you know this word?":
self-assessment reliably overshoots, and an inflated level is the exact failure
the whole level rework exists to fix.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.bot.states import InteractionState
from app.domain.enums import LearningTrack
from app.domain.levels import (
    TEST_LEVELS,
    TEST_PER_LEVEL,
    TEST_START_LEVEL,
    block_passed,
    next_test_level,
)
from app.domain.quiz_text import strip_latin_hints
from app.infrastructure.repositories.words import WordRepository
from app.services.interaction_state_service import InteractionStateService

OPTIONS_PER_CARD = 4

# Where the test was started from — the two entry points end differently: one
# closes onboarding, the other returns to settings.
ORIGIN_ONBOARDING = "onboarding"
ORIGIN_SETTINGS = "settings"
# Forced retake: an existing user who predates the test and is blocked
# until they take it. Ends by handing them the bot, not a settings screen.
ORIGIN_GATE = "gate"


@dataclass(frozen=True)
class PlacementCard:
    writing: str
    options: list[str]
    correct_index: int
    position: int  # 1-based, for "3 / 12"
    total: int


def _build_decks(
    words_by_level: dict[str, list[Any]], pool_by_level: dict[str, list[str]]
) -> dict[str, list[dict[str, Any]]]:
    """Quiz cards grouped by level, ready for the staircase to draw on.

    A card whose level has too few distinct translations to fill the options is
    dropped rather than padded from another level: a decoy from a different
    level is answerable by vibe, which would inflate the estimate.
    """
    decks: dict[str, list[dict[str, Any]]] = {}
    for level in TEST_LEVELS:
        words = words_by_level.get(level) or []
        pool = pool_by_level.get(level) or []
        for word in words:
            correct = strip_latin_hints(word.translation or "")
            if not correct:
                continue
            seen = {correct.lower()}
            decoys: list[str] = []
            for candidate in pool:
                shown = strip_latin_hints(candidate)
                if shown and shown.lower() not in seen:
                    seen.add(shown.lower())
                    decoys.append(shown)
                if len(decoys) == OPTIONS_PER_CARD - 1:
                    break
            if len(decoys) < OPTIONS_PER_CARD - 1:
                continue
            options = [correct, *decoys]
            random.shuffle(options)
            decks.setdefault(level, []).append(
                {
                    "level": level,
                    "writing": word.writing,
                    "options": options,
                    "correct": options.index(correct),
                }
            )
    return decks


class PlacementService:
    def __init__(self, words: WordRepository, state: InteractionStateService) -> None:
        self._words = words
        self._state = state

    async def start(
        self, user_id: int, track: LearningTrack, origin: str = ORIGIN_ONBOARDING
    ) -> PlacementCard | None:
        """Build the card pool and serve the first question, or None when the
        catalogue can't fill a fair test."""
        picked = await self._words.pick_placement_words(track, TEST_LEVELS, TEST_PER_LEVEL)
        pools: dict[str, list[str]] = {}
        for level, words in picked.items():
            pools[level] = await self._words.placement_translations(
                track,
                level,
                exclude_ids=[w.id for w in words],
                # Over-fetch: some candidates collide with the correct answer
                # or with each other and get dropped while filling a card.
                limit=TEST_PER_LEVEL * OPTIONS_PER_CARD * 2,
            )
        decks = _build_decks(picked, pools)
        level = TEST_START_LEVEL if decks.get(TEST_START_LEVEL) else next(iter(decks), None)
        if level is None:
            return None
        state = {
            "decks": decks,
            "level": level,
            "pos": 0,
            "flags": [],
            "tested": [],
            "verdict": TEST_LEVELS[0],
            "asked": 0,
            "origin": origin,
        }
        await self._state.set(user_id, InteractionState.ONBOARDING_LEVEL, state)
        return self._card(state)

    async def answer(self, user_id: int, chosen: int) -> tuple[PlacementCard | None, str | None]:
        """Record one answer and serve the next card, or finish.

        Returns (next card, verdict) — exactly one is set. The test walks levels
        rather than asking all of them: pass a block and it moves up, fail and
        it settles on the hardest level already held. Reaching B2 therefore
        means clearing A2 and B1 first, which is what stops a lucky block from
        promoting anyone.
        """
        payload = await self._state.get(user_id)
        if payload.state != InteractionState.ONBOARDING_LEVEL:
            return None, None
        state = payload.data
        decks: dict[str, list[dict[str, Any]]] = state.get("decks") or {}
        level = str(state.get("level") or "")
        deck = decks.get(level) or []
        pos = int(state.get("pos") or 0)
        if not deck or pos >= len(deck):
            return None, None

        state["flags"] = [*(state.get("flags") or []), chosen == deck[pos]["correct"]]
        state["pos"] = pos + 1
        state["asked"] = int(state.get("asked") or 0) + 1

        if state["pos"] < len(deck):
            await self._state.set(user_id, InteractionState.ONBOARDING_LEVEL, state)
            return self._card(state), None

        # Block finished — decide where the staircase goes next.
        tested = {*(state.get("tested") or []), level}
        nxt, verdict = next_test_level(level, block_passed(state["flags"]), tested)
        state["tested"] = sorted(tested)
        state["verdict"] = verdict
        if nxt is None or not decks.get(nxt):
            return None, verdict
        state.update(level=nxt, pos=0, flags=[])
        await self._state.set(user_id, InteractionState.ONBOARDING_LEVEL, state)
        return self._card(state), None

    async def origin_of(self, user_id: int) -> str:
        """Where the running test was started from — read before clearing state,
        so the handler knows which screen to return the user to."""
        payload = await self._state.get(user_id)
        return payload.data.get("origin") or ORIGIN_ONBOARDING

    @staticmethod
    def _card(state: dict[str, Any]) -> PlacementCard:
        deck = state["decks"][state["level"]]
        row = deck[int(state["pos"])]
        asked = int(state.get("asked") or 0)
        return PlacementCard(
            writing=row["writing"],
            options=list(row["options"]),
            correct_index=int(row["correct"]),
            position=asked + 1,
            # The total isn't known up front — the staircase stops as soon as
            # the level is bracketed — so this is the worst case, and the card
            # reads "3 of up to 12" rather than promising a fixed length.
            total=len(TEST_LEVELS) * TEST_PER_LEVEL,
        )
