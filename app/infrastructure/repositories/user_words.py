from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordSource, WordStatus
from app.domain.models import Pack, PackWord, UserWord, Word


class UserWordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_word_id: int) -> UserWord | None:
        return await self.session.get(UserWord, user_word_id)

    async def get_with_word(self, user_word_id: int) -> tuple[UserWord, Word] | None:
        result = await self.session.execute(
            select(UserWord, Word).join(Word, Word.id == UserWord.word_id).where(UserWord.id == user_word_id)
        )
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def bulk_add(
        self,
        user_id: int,
        track: LearningTrack,
        word_ids: Iterable[int],
        category_id: int | None,
        source: WordSource,
    ) -> int:
        """Add words to a user's vocabulary.

        Guarantees one (user_id, word_id) record per word — never duplicates.
        For words the user already has:
          - if their existing record has no category and a category is being
            requested now, set it (single canonical folder per word);
          - otherwise leave the existing record untouched.

        Returns the count of *newly added* rows (moves don't count).
        """
        ids = list({int(w) for w in word_ids})
        if not ids:
            return 0

        existing_q = select(UserWord).where(
            UserWord.user_id == user_id,
            UserWord.word_id.in_(ids),
        )
        existing_rows = list((await self.session.execute(existing_q)).scalars().all())
        existing_by_word: dict[int, UserWord] = {uw.word_id: uw for uw in existing_rows}

        if category_id is not None:
            for uw in existing_rows:
                if uw.category_id is None:
                    uw.category_id = category_id

        new_ids = [wid for wid in ids if wid not in existing_by_word]
        if not new_ids:
            await self.session.flush()
            return 0

        rows = [
            {
                "user_id": user_id,
                "word_id": wid,
                "track": track.value,
                "category_id": category_id,
                "source": source.value,
                "status": WordStatus.NEW.value,
            }
            for wid in new_ids
        ]
        await self.session.execute(pg_insert(UserWord).values(rows))
        await self.session.flush()
        return len(new_ids)

    async def list_for_user(
        self,
        user_id: int,
        track: LearningTrack,
        category_id: int | None = None,
        category_filter: str = "any",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[tuple[UserWord, Word]], int]:
        conditions = [UserWord.user_id == user_id, UserWord.track == track.value]
        if category_filter == "uncategorized":
            conditions.append(UserWord.category_id.is_(None))
        elif category_filter == "specific" and category_id is not None:
            conditions.append(UserWord.category_id == category_id)

        total_q = select(func.count(UserWord.id)).where(and_(*conditions))
        total = (await self.session.execute(total_q)).scalar_one()

        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(and_(*conditions))
            .order_by(UserWord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).all()
        return [(r[0], r[1]) for r in rows], total

    async def delete(self, user_word_id: int) -> None:
        uw = await self.get(user_word_id)
        if uw is None:
            return
        await self.session.delete(uw)
        await self.session.flush()

    async def pick_for_study(
        self,
        user_id: int,
        track: LearningTrack,
        limit: int,
        new_words_cap: int,
        category_id: int | None = None,
        scope: str = "goal",
        now: datetime | None = None,
    ) -> list[tuple[UserWord, Word]]:
        now = now or datetime.now(timezone.utc)
        base_conditions = [
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.status != WordStatus.MASTERED.value,
        ]
        if category_id is not None:
            base_conditions.append(UserWord.category_id == category_id)

        if scope == "weak":
            q = (
                select(UserWord, Word)
                .join(Word, Word.id == UserWord.word_id)
                .where(and_(*base_conditions, UserWord.mistakes_count > 0))
                .order_by(UserWord.mistakes_count.desc(), UserWord.ease_score.asc())
                .limit(limit)
            )
            return [(r[0], r[1]) for r in (await self.session.execute(q)).all()]

        if scope == "new":
            q = (
                select(UserWord, Word)
                .join(Word, Word.id == UserWord.word_id)
                .where(and_(*base_conditions, UserWord.status == WordStatus.NEW.value))
                .order_by(UserWord.created_at.asc())
                .limit(limit)
            )
            return [(r[0], r[1]) for r in (await self.session.execute(q)).all()]

        due_q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                and_(
                    *base_conditions,
                    UserWord.status != WordStatus.NEW.value,
                    UserWord.next_review_at <= now,
                )
            )
            .order_by(UserWord.next_review_at.asc())
            .limit(limit)
        )
        due = [(r[0], r[1]) for r in (await self.session.execute(due_q)).all()]
        remaining = limit - len(due)
        if remaining <= 0:
            return due

        new_limit = min(remaining, new_words_cap)
        new_q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(and_(*base_conditions, UserWord.status == WordStatus.NEW.value))
            .order_by(UserWord.created_at.asc())
            .limit(new_limit)
        )
        news = [(r[0], r[1]) for r in (await self.session.execute(new_q)).all()]
        return due + news

    async def count_weak(self, user_id: int, track: LearningTrack) -> int:
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.mistakes_count > 0,
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_status(self, user_id: int, track: LearningTrack, status: WordStatus) -> int:
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.status == status.value,
        )
        return (await self.session.execute(q)).scalar_one()

    async def total_for_user(self, user_id: int, track: LearningTrack) -> int:
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id, UserWord.track == track.value
        )
        return (await self.session.execute(q)).scalar_one()

    async def quiz_distractors(
        self,
        user_id: int,
        track: LearningTrack,
        exclude_user_word_id: int,
        limit: int = 3,
        exclude_translations: list[str] | None = None,
    ) -> list[str]:
        """Pick distractor translations for a quiz card.

        Prefer the user's own translated vocabulary (same context for them). If
        they're cold-starting and have <`limit` own translations, top up from
        translations of pack words in the same track. Never mix in other users'
        data.
        """
        excluded = {t for t in (exclude_translations or []) if t}

        own_q = (
            select(Word.translation)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.id != exclude_user_word_id,
                Word.translation.isnot(None),
            )
            .order_by(func.random())
            .limit(limit * 2)  # over-fetch to survive dedup against the right answer
        )
        own_rows = [r[0] for r in (await self.session.execute(own_q)).all() if r[0]]

        out: list[str] = []
        seen: set[str] = set(excluded)
        for t in own_rows:
            if t in seen:
                continue
            out.append(t)
            seen.add(t)
            if len(out) >= limit:
                return out

        if len(out) >= limit:
            return out

        remaining = limit - len(out)
        pack_q = (
            select(Word.translation)
            .join(PackWord, PackWord.word_id == Word.id)
            .join(Pack, Pack.id == PackWord.pack_id)
            .where(
                Pack.track == track.value,
                Pack.is_active.is_(True),
                Word.translation.isnot(None),
            )
            .order_by(func.random())
            .limit(remaining * 4)
        )
        pack_rows = [r[0] for r in (await self.session.execute(pack_q)).all() if r[0]]
        for t in pack_rows:
            if t in seen:
                continue
            out.append(t)
            seen.add(t)
            if len(out) >= limit:
                return out

        return out
