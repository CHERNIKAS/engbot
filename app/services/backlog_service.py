"""Offers to set aside words when someone's active pool has outgrown them.

Sizing the pool from measured throughput fixed the intake, not the backlog: a
user already holding sixty words against a ceiling of sixteen simply stops
receiving new ones until they grind through. That is the right direction and
far too slow — a word comes back every couple of weeks in the meantime, which
is exactly the state the ceiling exists to prevent.

Nothing here acts on its own. These are words the user chose to learn, so the
bot says what it sees and offers; the button is theirs to press. And it snoozes
rather than archives — parked words come back by themselves, and can be pulled
back sooner from «Архив и отложенные».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.pacing import MIN_POOL, POOL_TARGET_SHARE, overflow, pool_ceiling
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository

# Long enough that the pool actually drains before they return, short enough
# that a word the user still wants isn't gone for a season.
PARK_DAYS = 30


@dataclass(frozen=True)
class BacklogOffer:
    active: int
    target: int
    count: int  # how many to park

    @property
    def worth_offering(self) -> bool:
        return self.count > 0


class BacklogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._uw = UserWordRepository(session)
        self._reviews = WordReviewRepository(session)

    async def offer(self, user_id: int, track: LearningTrack) -> BacklogOffer:
        """What we'd propose, without doing any of it."""
        active = await self._uw.count_active(user_id, track)
        throughput = await self._reviews.typical_daily_answers(user_id, track)
        ceiling = pool_ceiling(throughput)
        target = max(MIN_POOL, round(ceiling * POOL_TARGET_SHARE))
        return BacklogOffer(active=active, target=target, count=overflow(active, ceiling))

    async def park(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> tuple[int, int]:
        """Set aside the least-progressed words. Returns (parked, still active).

        Recomputed rather than trusting the number on the button: the offer may
        have been sitting on screen while the user answered a few cards, and
        parking a stale count would take more than it should.
        """
        now = now or datetime.now(UTC)
        offer = await self.offer(user_id, track)
        if not offer.worth_offering:
            return 0, offer.active
        candidates = await self._uw.pick_backlog_to_park(
            user_id, track, limit=offer.count, now=now
        )
        parked = await self._uw.park_words(
            user_id,
            [uw.id for uw, _word in candidates],
            until=now + timedelta(days=PARK_DAYS),
        )
        return parked, offer.active - parked
