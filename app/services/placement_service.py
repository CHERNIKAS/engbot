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
from app.domain.levels import TEST_LEVELS, TEST_PER_LEVEL, estimate_level
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


def _build_deck(
    words_by_level: dict[str, list[Any]], pool_by_level: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Flatten the picked words into ordered quiz cards, easiest level first.

    A card whose level has too few distinct translations to fill the options is
    dropped rather than padded from another level: a decoy from a different
    level is answerable by vibe, which would inflate the estimate.
    """
    deck: list[dict[str, Any]] = []
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
            deck.append(
                {
                    "level": level,
                    "writing": word.writing,
                    "options": options,
                    "correct": options.index(correct),
                }
            )
    return deck


class PlacementService:
    def __init__(self, words: WordRepository, state: InteractionStateService) -> None:
        self._words = words
        self._state = state

    async def start(
        self, user_id: int, track: LearningTrack, origin: str = ORIGIN_ONBOARDING
    ) -> PlacementCard | None:
        """Build a deck and store it on the interaction state. None = the
        catalogue can't fill a fair test, and the caller should skip placement
        rather than show a broken one."""
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
        deck = _build_deck(picked, pools)
        if not deck:
            return None
        await self._state.set(
            user_id,
            InteractionState.ONBOARDING_LEVEL,
            {"deck": deck, "pos": 0, "answers": {}, "origin": origin},
        )
        return self._card(deck, 0)

    async def answer(self, user_id: int, chosen: int) -> tuple[PlacementCard | None, str | None]:
        """Record one answer. Returns (next card, verdict level) — exactly one
        of the two is set; a finished test returns (None, level)."""
        payload = await self._state.get(user_id)
        if payload.state != InteractionState.ONBOARDING_LEVEL:
            return None, None
        deck: list[dict[str, Any]] = payload.data.get("deck") or []
        pos = int(payload.data.get("pos") or 0)
        answers: dict[str, list[bool]] = payload.data.get("answers") or {}
        origin = payload.data.get("origin") or ORIGIN_ONBOARDING
        if not deck or pos >= len(deck):
            return None, None

        card = deck[pos]
        answers.setdefault(card["level"], []).append(chosen == card["correct"])
        pos += 1

        if pos >= len(deck):
            return None, estimate_level(answers)

        await self._state.set(
            user_id,
            InteractionState.ONBOARDING_LEVEL,
            {"deck": deck, "pos": pos, "answers": answers, "origin": origin},
        )
        return self._card(deck, pos), None

    async def origin_of(self, user_id: int) -> str:
        """Where the running test was started from — read before clearing state,
        so the handler knows which screen to return the user to."""
        payload = await self._state.get(user_id)
        return payload.data.get("origin") or ORIGIN_ONBOARDING

    @staticmethod
    def _card(deck: list[dict[str, Any]], pos: int) -> PlacementCard:
        row = deck[pos]
        return PlacementCard(
            writing=row["writing"],
            options=list(row["options"]),
            correct_index=int(row["correct"]),
            position=pos + 1,
            total=len(deck),
        )
