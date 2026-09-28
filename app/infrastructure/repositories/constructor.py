from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constructor import STALE
from app.domain.models import GrammarPhrase, GrammarTopic, UserGrammarTopic

# How many recently-served phrases to remember per topic. Long enough that a
# short set does not start repeating within a session; short enough that a
# topic with a hundred phrases still eventually reaches all of them.
RECENT_MEMORY = 20

# Just under the staleness line, so a failed check lands the topic in the
# "needs attention" band rather than at zero.
_FAILED_TEST_SCORE = STALE - 0.01


class ConstructorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def state(self, user_id: int, topic_id: int) -> UserGrammarTopic | None:
        return await self.session.get(UserGrammarTopic, (user_id, topic_id))

    async def ensure_state(self, user_id: int, topic_id: int) -> UserGrammarTopic:
        """The learner's row for this topic, created empty if missing.

        Upsert rather than select-then-insert: two grammar cards answered in
        the same second would otherwise race and one would fail on the primary
        key, losing an answer the learner definitely gave.
        """
        stmt = (
            pg_insert(UserGrammarTopic)
            .values(user_id=user_id, topic_id=topic_id)
            .on_conflict_do_nothing(index_elements=["user_id", "topic_id"])
        )
        await self.session.execute(stmt)
        await self.session.flush()
        row = await self.session.get(UserGrammarTopic, (user_id, topic_id))
        assert row is not None  # just inserted or already there
        return row

    async def pick_phrase(self, user_id: int, topic_id: int) -> GrammarPhrase | None:
        """The next sentence to build.

        Anything the learner has not seen lately comes first; within that, the
        authored order. Falls back to the whole set once everything is recent,
        which is what happens on a short topic — repeating is better than
        serving nothing, and the alternative is a card the plan cannot fill.
        """
        state = await self.state(user_id, topic_id)
        recent = [int(i) for i in (state.recent if state else []) or []]

        q = (
            select(GrammarPhrase)
            .where(GrammarPhrase.topic_id == topic_id)
            .order_by(GrammarPhrase.position.asc())
        )
        if recent:
            fresh = (await self.session.execute(q.where(GrammarPhrase.id.notin_(recent)))).scalars().first()
            if fresh is not None:
                return fresh
        return (await self.session.execute(q)).scalars().first()

    async def record_answer(
        self,
        user_id: int,
        topic_id: int,
        phrase_id: int,
        score: float,
        typing: bool | None = None,
        passed: bool = False,
    ) -> UserGrammarTopic:
        """Write the new score and remember the phrase.

        `typing` is only ever set to True — the mode is a ratchet. Passing the
        threshold and then dipping below it on the harder mode must not send
        the learner back to tapping pieces.
        """
        row = await self.ensure_state(user_id, topic_id)
        recent = [int(i) for i in (row.recent or [])]
        recent.append(int(phrase_id))
        row.recent = recent[-RECENT_MEMORY:]
        row.score = score
        row.answered = (row.answered or 0) + 1
        if typing:
            row.typing = True
        if passed and row.passed_at is None:
            row.passed_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return row

    async def active_topic(self, user_id: int) -> GrammarTopic | None:
        """The topic being learned: the first in teaching order the learner has
        not passed. Order comes from `position`, which is the curriculum — a
        learner must not meet question forms before the statement they invert.
        """
        passed = select(UserGrammarTopic.topic_id).where(
            UserGrammarTopic.user_id == user_id,
            UserGrammarTopic.passed_at.isnot(None),
        )
        # A topic with no phrases is skipped rather than blocking the ones
        # behind it. Without this, the first topic awaiting content stops the
        # curriculum dead: the plan keeps booking grammar slots, every card
        # comes back empty, and grammar disappears with nothing in the log.
        has_phrases = select(GrammarPhrase.id).where(GrammarPhrase.topic_id == GrammarTopic.id)
        q = (
            select(GrammarTopic)
            .where(GrammarTopic.id.notin_(passed), has_phrases.exists())
            .order_by(GrammarTopic.position.asc(), GrammarTopic.id.asc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def count_phrases(self, topic_id: int) -> int:
        q = select(func.count(GrammarPhrase.id)).where(GrammarPhrase.topic_id == topic_id)
        return (await self.session.execute(q)).scalar_one()

    async def get_phrase(self, phrase_id: int) -> GrammarPhrase | None:
        return await self.session.get(GrammarPhrase, phrase_id)

    async def test_phrases(self, topic_id: int, limit: int, exclude: list[int] | None = None) -> list[GrammarPhrase]:
        """Sentences for a check, avoiding what practice just used.

        Retaking on the same ten would measure those ten rather than the rule,
        which is also why a failed check is not offered again immediately.
        """
        q = select(GrammarPhrase).where(GrammarPhrase.topic_id == topic_id)
        if exclude:
            q = q.where(GrammarPhrase.id.notin_([int(i) for i in exclude]))
        rows = list((await self.session.execute(q.order_by(func.random()).limit(limit))).scalars().all())
        if len(rows) >= limit:
            return rows
        # A short topic cannot supply ten fresh ones. Repeating beats refusing
        # to check the topic at all.
        q2 = select(GrammarPhrase).where(GrammarPhrase.topic_id == topic_id)
        return list((await self.session.execute(q2.order_by(func.random()).limit(limit))).scalars().all())

    async def due_test_topic(self, user_id: int, now: datetime | None = None) -> GrammarTopic | None:
        """A passed topic whose check has come due, or None.

        Only one is ever returned: twenty-seven topics asking at once would
        turn a day into an examination sitting.
        """
        now = now or datetime.now(timezone.utc)
        q = (
            select(GrammarTopic)
            .join(UserGrammarTopic, UserGrammarTopic.topic_id == GrammarTopic.id)
            .where(
                UserGrammarTopic.user_id == user_id,
                UserGrammarTopic.passed_at.isnot(None),
                UserGrammarTopic.test_due_at.isnot(None),
                UserGrammarTopic.test_due_at <= now,
            )
            .order_by(UserGrammarTopic.test_due_at.asc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def record_test(
        self, user_id: int, topic_id: int, correct: int, held: bool, next_in_days: int
    ) -> UserGrammarTopic:
        row = await self.ensure_state(user_id, topic_id)
        now = datetime.now(timezone.utc)
        row.tested_at = now
        row.test_due_at = now + timedelta(days=next_in_days)
        row.held_streak = (row.held_streak or 0) + 1 if held else 0
        # A failed check does not revoke passing — it puts the topic back into
        # the day's rotation by dropping the score to where the stale rule sees
        # it. Revoking instead would make a bad five minutes undo months, and
        # the learner did pass it once.
        if not held:
            row.score = min(float(row.score or 0.0), _FAILED_TEST_SCORE)
        await self.session.flush()
        return row

    async def topics_with_progress(
        self, user_id: int
    ) -> list[tuple[GrammarTopic, UserGrammarTopic | None]]:
        """Every topic that has phrases, in teaching order, with the learner's
        row beside it.

        Topics without phrases are left out for the same reason `active_topic`
        skips them: they cannot be taught yet, and listing a lesson that never
        opens reads as something broken.
        """
        has_phrases = select(GrammarPhrase.id).where(GrammarPhrase.topic_id == GrammarTopic.id)
        q = (
            select(GrammarTopic, UserGrammarTopic)
            .outerjoin(
                UserGrammarTopic,
                (UserGrammarTopic.topic_id == GrammarTopic.id)
                & (UserGrammarTopic.user_id == user_id),
            )
            .where(has_phrases.exists())
            .order_by(GrammarTopic.position.asc(), GrammarTopic.id.asc())
        )
        return [(row[0], row[1]) for row in (await self.session.execute(q)).all()]
