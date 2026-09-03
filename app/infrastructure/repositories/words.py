from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack
from app.domain.models import UserWord, Word


def like_pattern(query: str) -> str:
    """A %query% ILIKE pattern with the LIKE metacharacters escaped, so a user
    typing '100%' searches for a literal percent sign."""
    escaped = (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


class WordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_catalog(
        self, track: LearningTrack, query: str, exclude_user_id: int, limit: int = 5
    ) -> list[Word]:
        """Catalog words matching the query (by writing or translation) that the
        user does NOT own yet — candidates to add from search. Exact writing
        match ranks first, then shorter writings (closest matches)."""
        pattern = like_pattern(query)
        owned = select(UserWord.word_id).where(
            UserWord.user_id == exclude_user_id, UserWord.track == track.value
        )
        exact_first = case(
            (func.lower(Word.writing) == query.lower(), 0), else_=1
        )
        q = (
            select(Word)
            .where(
                Word.track == track.value,
                Word.translation.isnot(None),
                Word.id.not_in(owned),
                or_(
                    Word.writing.ilike(pattern),
                    Word.normalized_word.ilike(pattern),
                    Word.translation.ilike(pattern),
                ),
            )
            .order_by(exact_first, func.length(Word.writing), Word.writing)
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def get(self, word_id: int) -> Word | None:
        return await self.session.get(Word, word_id)

    async def get_by_normalized(self, track: LearningTrack, normalized: str) -> Word | None:
        result = await self.session.execute(
            select(Word).where(Word.track == track.value, Word.normalized_word == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_normalized_many(
        self, track: LearningTrack, normalized: Iterable[str]
    ) -> dict[str, Word]:
        keys = list({n for n in normalized if n})
        if not keys:
            return {}
        result = await self.session.execute(
            select(Word).where(Word.track == track.value, Word.normalized_word.in_(keys))
        )
        return {w.normalized_word: w for w in result.scalars().all()}

    async def upsert_many(self, track: LearningTrack, items: list[dict]) -> dict[str, Word]:
        """Insert words for the given track if missing. Returns normalized -> Word."""
        if not items:
            return {}

        rows = [{**item, "track": track.value} for item in items]
        stmt = (
            pg_insert(Word)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["track", "normalized_word"])
        )
        await self.session.execute(stmt)
        await self.session.flush()

        return await self.get_by_normalized_many(
            track, [i["normalized_word"] for i in rows]
        )

    async def update_example_if_empty(self, word_id: int, example: str) -> None:
        word = await self.get(word_id)
        if word is None or word.example_sentence:
            return
        word.example_sentence = example
        await self.session.flush()

    async def pick_placement_words(
        self, track: LearningTrack, levels: Iterable[str], per_level: int
    ) -> dict[str, list[Word]]:
        """Words for the onboarding placement test, grouped by CEFR level.

        Only common single words qualify. Rarity would measure vocabulary
        trivia rather than level (plenty of B1 learners have never met
        "plummet"), and a multi-word phrase is recognised from its parts, so
        both would push the estimate around for the wrong reasons.

        Randomised per run so retaking the test isn't answering from memory.
        """
        picked: dict[str, list[Word]] = {}
        for level in levels:
            q = (
                select(Word)
                .where(
                    Word.track == track.value,
                    Word.level == level,
                    Word.translation.isnot(None),
                    Word.writing.not_like("% %"),
                    or_(Word.freq_rank.is_(None), Word.freq_rank <= 3),
                )
                .order_by(func.random())
                .limit(per_level)
            )
            rows = list((await self.session.execute(q)).scalars().all())
            if rows:
                picked[level] = rows
        return picked

    async def placement_translations(
        self, track: LearningTrack, level: str, exclude_ids: Iterable[int], limit: int
    ) -> list[str]:
        """Translations at one level, for the placement test's wrong options.

        Deliberately not `quiz_distractors`: that one draws from the user's own
        vocabulary, which during onboarding is empty, and it excludes by
        user_word id — a placement word has no such row. Same-level options also
        matter more here, since an obviously easy decoy would let someone pass a
        level by elimination.
        """
        q = (
            select(Word.translation)
            .where(
                Word.track == track.value,
                Word.level == level,
                Word.translation.isnot(None),
                Word.id.not_in(list(exclude_ids) or [0]),
            )
            .order_by(func.random())
            .limit(limit)
        )
        return [t for t in (await self.session.execute(q)).scalars().all() if t]
