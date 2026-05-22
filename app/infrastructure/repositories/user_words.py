from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordSource, WordStatus
from app.domain.models import Pack, PackWord, UserWord, Word

_TOKEN_SEPARATORS = "/,;()"


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _meaning_tokens(translation: str) -> set[str]:
    """Content words of a translation, for detecting overlapping meanings.
    «хранить / держать» -> {хранить, держать}; «ждать с нетерпением» -> {ждать,
    нетерпением}. Tokens of length <= 2 (prepositions, single letters) are
    dropped so they can't cause spurious overlaps."""
    s = translation.lower()
    for sep in _TOKEN_SEPARATORS:
        s = s.replace(sep, " ")
    return {tok for tok in s.split() if len(tok) > 2}


def _meaning_tokens_of(translations: list[str]) -> set[str]:
    out: set[str] = set()
    for t in translations:
        if t:
            out |= _meaning_tokens(t)
    return out


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

    async def pick_for_push(
        self,
        user_id: int,
        track: LearningTrack,
        new_quota_left: int,
        exclude_uw_id: int = 0,
        now: datetime | None = None,
    ) -> tuple[UserWord, Word, bool] | None:
        """Pick one word for a push: a due review first, else a new word (if the
        daily new-quota allows). Returns (user_word, word, is_new) or None.
        Only words that have a translation (quizzable)."""
        now = now or datetime.now(timezone.utc)
        base = [
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.status != WordStatus.MASTERED.value,
            Word.translation.isnot(None),
        ]
        if exclude_uw_id:
            base.append(UserWord.id != exclude_uw_id)

        due_q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(and_(*base, UserWord.status != WordStatus.NEW.value, UserWord.next_review_at <= now))
            .order_by(UserWord.next_review_at.asc())
            .limit(1)
        )
        row = (await self.session.execute(due_q)).first()
        if row is not None:
            return row[0], row[1], False

        if new_quota_left > 0:
            new_q = (
                select(UserWord, Word)
                .join(Word, Word.id == UserWord.word_id)
                .where(and_(*base, UserWord.status == WordStatus.NEW.value))
                .order_by(UserWord.created_at.asc())
                .limit(1)
            )
            row = (await self.session.execute(new_q)).first()
            if row is not None:
                return row[0], row[1], True
        return None

    async def count_active(self, user_id: int, track: LearningTrack) -> int:
        """Words the user is currently learning (started, not yet mastered,
        not archived). This is the 'active set' the push engine keeps at
        daily_goal size."""
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
        )
        return (await self.session.execute(q)).scalar_one()

    async def pick_new_for_push(
        self, user_id: int, track: LearningTrack
    ) -> tuple[UserWord, Word] | None:
        """One brand-new (unstudied) quizzable word, oldest first — to introduce
        into the active set when a slot frees up."""
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status == WordStatus.NEW.value,
                Word.translation.isnot(None),
            )
            .order_by(UserWord.created_at.asc())
            .limit(1)
        )
        row = (await self.session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None

    async def pick_active_random(
        self, user_id: int, track: LearningTrack
    ) -> tuple[UserWord, Word] | None:
        """A random word from the active set (being learned) — for reinforcement."""
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
                Word.translation.isnot(None),
            )
            .order_by(func.random())
            .limit(1)
        )
        row = (await self.session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None

    async def pick_review_mastered(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> tuple[UserWord, Word] | None:
        """A mastered ('learned') word for review — not archived, not snoozed.
        Weighted random so a LOWER score is shown more often, 5.0 rarely."""
        now = now or datetime.now(timezone.utc)
        # weight = 5.2 - score (low score -> big weight). A-Res weighted sampling:
        # order by random()^(1/weight) desc, take the top one.
        weight = 5.2 - UserWord.mastery_score
        key = func.power(func.random(), 1.0 / weight)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status == WordStatus.MASTERED.value,
                or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
                Word.translation.isnot(None),
            )
            .order_by(key.desc())
            .limit(1)
        )
        row = (await self.session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None

    async def has_managed(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> bool:
        """Whether the user has any archived or currently-snoozed words (to show
        the management entry on the Progress screen)."""
        now = now or datetime.now(timezone.utc)
        q = (
            select(UserWord.id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                or_(
                    UserWord.archived.is_(True),
                    and_(UserWord.snooze_until.isnot(None), UserWord.snooze_until > now),
                ),
            )
            .limit(1)
        )
        return (await self.session.execute(q)).first() is not None

    async def list_archived(
        self, user_id: int, track: LearningTrack, limit: int = 30
    ) -> list[tuple[UserWord, Word]]:
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(True),
            )
            .order_by(UserWord.id.desc())
            .limit(limit)
        )
        return [(r[0], r[1]) for r in (await self.session.execute(q)).all()]

    async def list_snoozed(
        self, user_id: int, track: LearningTrack, now: datetime | None = None, limit: int = 30
    ) -> list[tuple[UserWord, Word]]:
        now = now or datetime.now(timezone.utc)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.snooze_until.isnot(None),
                UserWord.snooze_until > now,
            )
            .order_by(UserWord.snooze_until.asc())
            .limit(limit)
        )
        return [(r[0], r[1]) for r in (await self.session.execute(q)).all()]

    async def remove_by_word_ids(
        self, user_id: int, track: LearningTrack, word_ids: list[int]
    ) -> int:
        """Delete the user's records for these words (removes them from learning,
        dropping their progress). Returns how many were removed."""
        if not word_ids:
            return 0
        result = await self.session.execute(
            delete(UserWord).where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.word_id.in_(word_ids),
            )
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def status_map(
        self, user_id: int, track: LearningTrack, word_ids: list[int]
    ) -> dict[int, str]:
        """{word_id: status} for the user's owned words among `word_ids`. Words
        the user doesn't own are absent. Used by the course to decide top-ups."""
        if not word_ids:
            return {}
        q = select(UserWord.word_id, UserWord.status).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.word_id.in_(word_ids),
        )
        return {int(r[0]): str(r[1]) for r in (await self.session.execute(q)).all()}

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

    async def existing_normalized(
        self, user_id: int, track: LearningTrack, normalized: list[str]
    ) -> set[str]:
        """Which of these normalized words the user already has (for honest
        import previews — already-owned words won't be added again)."""
        if not normalized:
            return set()
        q = (
            select(Word.normalized_word)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                Word.normalized_word.in_(normalized),
            )
        )
        return {row[0] for row in (await self.session.execute(q)).all()}

    async def quiz_distractors(
        self,
        user_id: int,
        track: LearningTrack,
        exclude_user_word_id: int,
        limit: int = 3,
        exclude_translations: list[str] | None = None,
        correct_pos: str | None = None,
        correct_level: str | None = None,
    ) -> list[str]:
        """Pick distractor translations for a quiz card.

        Candidates come from the user's own translated vocabulary first (same
        context for them); on a cold start (<`limit` usable own translations) we
        top up from pack words in the same track. Never mix in other users' data.

        Quality:
        - candidates are ranked so that the same part of speech / level as the
          answer come first (a verb is quizzed against verbs, not random nouns);
        - a candidate that shares a meaning word with the correct answer is
          dropped, so we never offer a translation that's actually also correct
          (e.g. «держать» as a distractor when the answer is «хранить / держать»).
        """
        protected = _meaning_tokens_of(exclude_translations or [])
        seen: set[str] = {_norm(t) for t in (exclude_translations or []) if t}

        def tier(pos: str | None, level: str | None) -> int:
            pos_match = correct_pos is not None and pos == correct_pos
            level_match = correct_level is not None and level == correct_level
            if pos_match and level_match:
                return 0
            if pos_match:
                return 1
            if level_match:
                return 2
            return 3

        candidates: list[tuple[int, str]] = []

        def consider(rows: list) -> None:
            for translation, pos, level in rows:
                if not translation:
                    continue
                n = _norm(translation)
                if n in seen:
                    continue
                if _meaning_tokens(translation) & protected:
                    continue  # shares a meaning with the answer -> would be valid
                seen.add(n)
                candidates.append((tier(pos, level), translation))

        own_q = (
            select(Word.translation, Word.part_of_speech, Word.level)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.id != exclude_user_word_id,
                Word.translation.isnot(None),
            )
            .order_by(func.random())
            .limit(limit * 4)  # over-fetch for dedup + tier variety
        )
        consider(list((await self.session.execute(own_q)).all()))

        # Only reach for pack words when the user's own vocab can't fill the card.
        if len(candidates) < limit:
            pack_q = (
                select(Word.translation, Word.part_of_speech, Word.level)
                .join(PackWord, PackWord.word_id == Word.id)
                .join(Pack, Pack.id == PackWord.pack_id)
                .where(
                    Pack.track == track.value,
                    Pack.is_active.is_(True),
                    Word.translation.isnot(None),
                )
                .order_by(func.random())
                .limit(limit * 8)
            )
            consider(list((await self.session.execute(pack_q)).all()))

        # Stable sort keeps own-before-pack and random order within a tier.
        candidates.sort(key=lambda c: c[0])
        return [translation for _, translation in candidates[:limit]]
