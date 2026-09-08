"""Re-scores answers that were marked strictly because the checker was down.

When the API can't be reached, a typed answer falls back to exact-match and the
card says so. That is honest, but it costs the user credit they had earned: a
typo on a long word is a slip, not a miss, and being told otherwise because a
third-party service was busy is the bot's problem, not theirs.

So the answer is parked instead of forgotten. When the checker is reachable
again a worker re-runs it, applies whatever credit it should have given, and
tells the user what changed. The user loses time, never progress.

Only under-scoring is corrected. A strict miss that turns out to be a real miss
changes nothing, and credit is never taken away after the fact — finding out
that yesterday's success has been revoked is worse than never having had it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import mastery
from app.infrastructure.repositories.user_words import UserWordRepository
from app.logging_setup import get_logger
from app.services.answer_check import AnswerCheckService

log = get_logger("regrade")

QUEUE_KEY = "regrade:pending"
# A parked answer more than a day old isn't worth resurrecting: the user has
# moved on, and a surprise "your answer from Tuesday was fine" is noise.
MAX_AGE_SECONDS = 86_400
# Cap the queue so a long outage can't grow it without bound.
MAX_QUEUE = 500


@dataclass(frozen=True)
class ParkedAnswer:
    user_id: int
    telegram_id: int
    user_word_id: int
    word: str
    translation: str
    answer: str
    at: float


class RegradeQueue:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def park(self, item: ParkedAnswer) -> None:
        """Remember an answer that was scored without the checker."""
        try:
            await self._redis.lpush(QUEUE_KEY, json.dumps(asdict(item), ensure_ascii=False))
            await self._redis.ltrim(QUEUE_KEY, 0, MAX_QUEUE - 1)
        except Exception:  # noqa: BLE001 — parking is best-effort, never break the answer
            log.warning("regrade_park_failed", user_word_id=item.user_word_id)

    async def drain(self, limit: int) -> list[ParkedAnswer]:
        """Take up to `limit` parked answers off the queue."""
        out: list[ParkedAnswer] = []
        for _ in range(limit):
            raw = await self._redis.rpop(QUEUE_KEY)
            if raw is None:
                break
            try:
                data: dict[str, Any] = json.loads(raw)
                out.append(ParkedAnswer(**data))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue  # malformed entry: drop it rather than block the queue
        return out

    async def pending(self) -> int:
        try:
            return int(await self._redis.llen(QUEUE_KEY))
        except Exception:  # noqa: BLE001
            return 0


@dataclass
class RegradeResult:
    checked: int = 0
    upgraded: int = 0
    per_user: dict[int, list[str]] = None  # telegram_id -> lines to send
    # Everyone whose parked answers were re-run, upgraded or not. The user was
    # told "засчитываю строго, вернётся сама, ответ пересчитаю" — so the promise
    # is owed an answer either way. Silence after that reads as a promise
    # quietly dropped, even when the recheck agreed the miss was a miss.
    rechecked: set[int] = None  # telegram_ids

    def __post_init__(self) -> None:
        if self.per_user is None:
            self.per_user = {}
        if self.rechecked is None:
            self.rechecked = set()


class RegradeService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._queue = RegradeQueue(redis)
        self._checker = AnswerCheckService(redis)
        self._uw = UserWordRepository(session)

    async def run(self, now: float, limit: int = 50) -> RegradeResult:
        result = RegradeResult()
        if not self._checker.enabled:
            return result
        for item in await self._queue.drain(limit):
            if now - item.at > MAX_AGE_SECONDS:
                continue
            verdict = await self._checker.classify(item.word, item.translation, item.answer)
            if verdict is None:
                # Still unreachable — put it back and stop; hammering a dead API
                # would just empty the queue into nothing.
                await self._queue.park(item)
                break
            result.checked += 1
            result.rechecked.add(item.telegram_id)
            if not verdict.credited:
                continue
            uw = await self._uw.get(item.user_word_id, owner_id=item.user_id)
            if uw is None:
                continue
            uw.learning_score = mastery.apply_credit(uw.learning_score or 0.0, verdict.kind)
            if mastery.is_production(verdict.kind):
                uw.production_count = (uw.production_count or 0) + 1
            result.upgraded += 1
            result.per_user.setdefault(item.telegram_id, []).append(
                f"«{item.answer}» → {item.word}: {verdict.hint}" if verdict.hint
                else f"«{item.answer}» → {item.word}"
            )
        if result.upgraded:
            await self._session.flush()
            log.info("regrade_applied", upgraded=result.upgraded, checked=result.checked)
        return result
