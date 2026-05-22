from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordStatus
from app.domain.models import GrammarItem, GrammarTopic, UserGrammarItem, UserGrammarTopic


class GrammarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_item(self, ugi_id: int) -> UserGrammarItem | None:
        return await self.session.get(UserGrammarItem, ugi_id)

    async def next_unstarted_topic(
        self, user_id: int, track: LearningTrack
    ) -> GrammarTopic | None:
        """The next topic (by position) the user has not started yet."""
        started = (
            select(GrammarItem.topic_id)
            .join(UserGrammarItem, UserGrammarItem.grammar_item_id == GrammarItem.id)
            .where(UserGrammarItem.user_id == user_id)
            .distinct()
        )
        q = (
            select(GrammarTopic)
            .where(GrammarTopic.track == track.value, GrammarTopic.id.notin_(started))
            .order_by(GrammarTopic.position.asc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def active_topic(self, user_id: int, track: LearningTrack) -> GrammarTopic | None:
        """A topic the user is mid-way through (has a non-mastered item)."""
        q = (
            select(GrammarTopic)
            .join(GrammarItem, GrammarItem.topic_id == GrammarTopic.id)
            .join(UserGrammarItem, UserGrammarItem.grammar_item_id == GrammarItem.id)
            .where(
                GrammarTopic.track == track.value,
                UserGrammarItem.user_id == user_id,
                UserGrammarItem.status != WordStatus.MASTERED.value,
            )
            .order_by(GrammarTopic.position.asc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def introduce_topic(self, user_id: int, topic_id: int) -> int:
        """Create per-user progress rows (status NEW) for every exercise in the
        topic, plus a rule-tracking row (rule_seen_at NULL). Idempotent."""
        item_ids = [
            r[0]
            for r in (
                await self.session.execute(
                    select(GrammarItem.id).where(GrammarItem.topic_id == topic_id)
                )
            ).all()
        ]
        if item_ids:
            await self.session.execute(
                pg_insert(UserGrammarItem)
                .values([{"user_id": user_id, "grammar_item_id": iid, "status": WordStatus.NEW.value} for iid in item_ids])
                .on_conflict_do_nothing(index_elements=["user_id", "grammar_item_id"])
            )
        await self.session.execute(
            pg_insert(UserGrammarTopic)
            .values(user_id=user_id, topic_id=topic_id, rule_seen_at=None)
            .on_conflict_do_nothing(index_elements=["user_id", "topic_id"])
        )
        await self.session.flush()
        return len(item_ids)

    async def pending_rule(self, user_id: int, track: LearningTrack) -> GrammarTopic | None:
        """A topic whose rule hasn't been shown to the user yet."""
        q = (
            select(GrammarTopic)
            .join(UserGrammarTopic, UserGrammarTopic.topic_id == GrammarTopic.id)
            .where(
                GrammarTopic.track == track.value,
                UserGrammarTopic.user_id == user_id,
                UserGrammarTopic.rule_seen_at.is_(None),
            )
            .order_by(GrammarTopic.position.asc())
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def mark_rule_seen(self, user_id: int, topic_id: int) -> None:
        ugt = await self.session.get(UserGrammarTopic, (user_id, topic_id))
        if ugt is not None:
            ugt.rule_seen_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def pick_for_push(
        self, user_id: int, track: LearningTrack
    ) -> tuple[UserGrammarItem, GrammarItem] | None:
        """A random non-mastered grammar exercise for the user (new or learning)."""
        q = (
            select(UserGrammarItem, GrammarItem)
            .join(GrammarItem, GrammarItem.id == UserGrammarItem.grammar_item_id)
            .join(GrammarTopic, GrammarTopic.id == GrammarItem.topic_id)
            .where(
                UserGrammarItem.user_id == user_id,
                UserGrammarItem.status != WordStatus.MASTERED.value,
                GrammarTopic.track == track.value,
            )
            .order_by(func.random())
            .limit(1)
        )
        row = (await self.session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None

    async def item_with_progress(
        self, ugi_id: int
    ) -> tuple[UserGrammarItem, GrammarItem] | None:
        q = (
            select(UserGrammarItem, GrammarItem)
            .join(GrammarItem, GrammarItem.id == UserGrammarItem.grammar_item_id)
            .where(UserGrammarItem.id == ugi_id)
        )
        row = (await self.session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None
