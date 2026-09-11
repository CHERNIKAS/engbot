from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LearningTrack, WordSource, WordStatus
from app.domain.levels import (
    DEFAULT_SOURCE_PRIORITY,
    LEVELS,
    SOURCE_PRIORITY,
    UNKNOWN_LEVEL_RANK,
    index,
    normalize,
    selection_rank,
)
from app.domain.models import Pack, PackWord, UserWord, Word
from app.domain.quiz_text import strip_latin_hints

# How many best-fitting candidates to shuffle between when introducing a new
# word. Wide enough that the head of the queue varies, narrow enough that every
# pick still comes from the right difficulty band.
NEW_PICK_WINDOW = 8

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


def _is_negation(translation: str) -> bool:
    """A Russian negation gloss («не имею», «ни один»). Used to keep distractors
    the same SHAPE as the answer — a negation is quizzed against other negations
    (don't/can't/isn't) instead of a random noun the user can pick by elimination."""
    n = _norm(translation)
    return n.startswith("не ") or n.startswith("ни ")


def _first_token(translation: str) -> str:
    s = translation.lower()
    for sep in _TOKEN_SEPARATORS:
        s = s.replace(sep, " ")
    tokens = s.split()
    return tokens[0] if tokens else ""


def _shape_signature(shown: str) -> tuple[bool, ...]:
    """The option's features VISIBLE without knowing any English. A corpus audit
    showed 18% of cards were solvable by eye: the correct option was the only
    one with a slash («вопрос / проблема» vs three plain nouns), the only
    multi-word one, the only infinitive, etc. Distractors are ranked by how
    many of these bits they share with the answer, so the correct option
    doesn't stand out."""
    first = _first_token(shown)
    return (
        "/" in shown,
        len(shown.split()) > 1,
        len(first) > 3 and first.endswith(("ть", "ться", "ти", "чь")),
        len(first) > 3 and first.endswith(("ый", "ий", "ой", "ая", "яя", "ое", "ее")),
        "(" in shown,
        bool(shown) and shown[0].isupper(),
    )


def _shape_distance(a: tuple[bool, ...], b: tuple[bool, ...]) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def _pick_avoiding(
    rows: list[tuple[UserWord, Word]], exclude_uw_id: int
) -> tuple[UserWord, Word] | None:
    """From a small over-fetched candidate list, return one that isn't the
    just-shown card (`exclude_uw_id`) so the same word doesn't come back-to-back.
    Falls back to the excluded one only when it's the sole candidate."""
    if not rows:
        return None
    for uw, word in rows:
        if uw.id != exclude_uw_id:
            return uw, word
    return rows[0]


class UserWordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_word_id: int, owner_id: int | None = None) -> UserWord | None:
        """Load a UserWord by id. Pass `owner_id` to scope by owner — any handler
        acting on a client-supplied id MUST, or a forged callback can touch
        another user's row (returns None if the id isn't theirs)."""
        uw = await self.session.get(UserWord, user_word_id)
        if uw is None or (owner_id is not None and uw.user_id != owner_id):
            return None
        return uw

    async def get_with_word(
        self, user_word_id: int, owner_id: int | None = None
    ) -> tuple[UserWord, Word] | None:
        conds = [UserWord.id == user_word_id]
        if owner_id is not None:
            conds.append(UserWord.user_id == owner_id)
        result = await self.session.execute(
            select(UserWord, Word).join(Word, Word.id == UserWord.word_id).where(*conds)
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

    async def delete(self, user_word_id: int, owner_id: int | None = None) -> None:
        uw = await self.get(user_word_id, owner_id=owner_id)
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
            # Words the user hid («перестать показывать») or parked as leeches
            # must stay out of drills too — otherwise a hidden word keeps being
            # quizzed and can even reach MASTERED while archived (invisible to
            # the ⭐ counter).
            UserWord.archived.is_(False),
            or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
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

    async def count_active(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> int:
        """Words the user is currently learning (started, not yet mastered, not
        archived, not snoozed). This is the 'active pool' the push engine keeps
        under the intake ceiling — a snoozed leech frees its slot."""
        now = now or datetime.now(timezone.utc)
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
            or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_overdue(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> int:
        """Active words already due for review (next_review_at in the past). When
        this backlog is large the push should drain it before introducing new
        words — otherwise new intake outruns review and every word surfaces only
        once a week, so mastery crawls."""
        now = now or datetime.now(timezone.utc)
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
            or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
            UserWord.next_review_at <= now,
        )
        return (await self.session.execute(q)).scalar_one()

    async def set_priority(self, user_id: int, word_ids: Iterable[int], value: bool = True) -> int:
        """Flag words as "teach first" for one user. Scoped by user_id so a
        forged id list can't touch anyone else's rows."""
        ids = [int(w) for w in word_ids]
        if not ids:
            return 0
        result = await self.session.execute(
            update(UserWord)
            .where(UserWord.user_id == user_id, UserWord.word_id.in_(ids))
            .values(priority=value)
        )
        await self.session.flush()
        return result.rowcount or 0

    async def pick_new_for_push(
        self, user_id: int, track: LearningTrack, user_level: str | None = None
    ) -> tuple[UserWord, Word] | None:
        """One brand-new (unstudied) quizzable word to introduce when a slot
        frees up — chosen by how well it fits the user, not by when it arrived.

        This used to be `order_by(created_at)`, which handed words out in
        whatever order they were imported: a TXT file's line order, or a pack's
        migration order. With ~4k words sitting in NEW that meant the queue was
        effectively arbitrary, and nothing ever looked at difficulty.

        Ordering now: distance from the user's level first (see
        `levels.selection_rank`), then common words before rare ones, then the
        user's own additions ahead of catalogue filler, then age as a stable
        tiebreak. The final pick is random inside a small head window so the
        same word doesn't sit at the front of the queue forever — the ordering
        decides the band, not the exact word.
        """
        level_rank = case(
            {lv: selection_rank(lv, user_level) for lv in LEVELS},
            value=Word.level,
            else_=UNKNOWN_LEVEL_RANK,
        )
        source_priority = case(
            SOURCE_PRIORITY, value=UserWord.source, else_=DEFAULT_SOURCE_PRIORITY
        )
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status == WordStatus.NEW.value,
                Word.translation.isnot(None),
                Word.is_function_word.is_(False),
            )
            .order_by(
                # The user's own "teach this first" beats every other signal —
                # it's the one place they've told us directly what they want.
                UserWord.priority.desc(),
                level_rank,
                # NULLS LAST: an untagged word shouldn't read as "maximally
                # common" just because its rank was never filled in.
                Word.freq_rank.asc().nulls_last(),
                source_priority,
                UserWord.created_at.asc(),
            )
            .limit(NEW_PICK_WINDOW)
        )
        rows = (await self.session.execute(q)).all()
        if not rows:
            return None
        row = random.choice(rows)
        return (row[0], row[1])

    async def pick_backlog_to_park(
        self, user_id: int, track: LearningTrack, limit: int, now: datetime | None = None
    ) -> list[tuple[UserWord, Word]]:
        """The active words furthest from being learned, worst first.

        When a pool is too big for its owner, the words to set aside are the
        ones that have gone nowhere — lowest score, never typed, longest
        untouched. Parking a word that is nearly finished would waste the work
        already in it, which is the opposite of the point.

        Snoozed words are excluded: they're already out of rotation.
        """
        now = now or datetime.now(timezone.utc)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
                or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
            )
            .order_by(
                UserWord.learning_score.asc(),
                UserWord.production_count.asc(),
                UserWord.last_reviewed_at.asc().nulls_first(),
            )
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await self.session.execute(q)).all()]

    async def park_words(
        self, user_id: int, user_word_ids: Iterable[int], until: datetime
    ) -> int:
        """Snooze, not archive: the user gets these back on their own, and
        they're listed under «Архив и отложенные» in the meantime."""
        ids = [int(i) for i in user_word_ids]
        if not ids:
            return 0
        result = await self.session.execute(
            update(UserWord)
            .where(UserWord.user_id == user_id, UserWord.id.in_(ids))
            .values(snooze_until=until)
        )
        await self.session.flush()
        return result.rowcount or 0

    async def level_evidence(
        self, user_id: int, track: LearningTrack, user_level: str | None
    ) -> tuple[int, int, int]:
        """Evidence for recalibrating the user's level:
        (mastered at or above their level, attempts at their level, of those correct).

        Attempts are counted from `repetitions_count + mistakes_count` rather
        than the review log, which is cheaper and covers the word's whole life
        instead of one retention window — recalibration is about the long run.
        Untagged words are left out entirely: counting them as at-level would
        let a pile of unclassified imports promote someone on no evidence.
        """
        at_or_above = [lv for lv in LEVELS if index(lv) >= index(user_level)]
        mastered_q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status == WordStatus.MASTERED.value,
            UserWord.word_id.in_(
                select(Word.id).where(Word.track == track.value, Word.level.in_(at_or_above))
            ),
        )
        mastered = (await self.session.execute(mastered_q)).scalar_one() or 0

        at_level_q = select(
            func.coalesce(func.sum(UserWord.repetitions_count + UserWord.mistakes_count), 0),
            func.coalesce(func.sum(UserWord.repetitions_count), 0),
        ).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.word_id.in_(
                select(Word.id).where(
                    Word.track == track.value, Word.level == normalize(user_level)
                )
            ),
        )
        attempts, correct = (await self.session.execute(at_level_q)).one()
        return int(mastered), int(attempts or 0), int(correct or 0)

    async def pick_active_due(
        self, user_id: int, track: LearningTrack, exclude_uw_id: int = 0, now: datetime | None = None
    ) -> tuple[UserWord, Word] | None:
        """The active word most overdue for review (earliest next_review_at) —
        for reinforcement. Uniform random starved big pools (a word could go
        unseen for weeks while just-seen ones repeated); due-first makes the SR
        intervals real: a lapsed word comes back within hours, a solid one waits
        its turn. Skips snoozed (parked-leech) words. Over-fetches a few so we
        can skip `exclude_uw_id` (the card just answered) — answering pushes
        next_review_at forward, so this can't lock onto one word."""
        now = now or datetime.now(timezone.utc)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
                or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
                Word.translation.isnot(None),
                Word.is_function_word.is_(False),
            )
            .order_by(UserWord.next_review_at.asc())
            .limit(5)
        )
        rows = [(r[0], r[1]) for r in (await self.session.execute(q)).all()]
        return _pick_avoiding(rows, exclude_uw_id)

    async def search_own(
        self, user_id: int, track: LearningTrack, query: str, limit: int = 5
    ) -> list[tuple[UserWord, Word]]:
        """The user's own words matching the query — by English writing, the
        pack translation or their custom one. Exact writing match first, then
        shorter (closer) matches."""
        from app.infrastructure.repositories.words import like_pattern

        pattern = like_pattern(query)
        exact_first = case((func.lower(Word.writing) == query.lower(), 0), else_=1)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                or_(
                    Word.writing.ilike(pattern),
                    Word.normalized_word.ilike(pattern),
                    Word.translation.ilike(pattern),
                    UserWord.custom_translation.ilike(pattern),
                ),
            )
            .order_by(exact_first, func.length(Word.writing), Word.writing)
            .limit(limit)
        )
        return [(r[0], r[1]) for r in (await self.session.execute(q)).all()]

    async def pick_review_mastered(
        self, user_id: int, track: LearningTrack, now: datetime | None = None, exclude_uw_id: int = 0
    ) -> tuple[UserWord, Word] | None:
        """A mastered ('learned') word that is DUE for review — not archived, not
        snoozed, and past its next_review_at. Most overdue first; among equally
        due words, the weaker one (lower mastery_score) goes first.

        This used to pick by weighted random over EVERY mastered word and never
        looked at next_review_at at all. With every word sitting at 5.0 the
        weights were equal, so the "review" stream (~1 card in 5) drew uniformly
        from the whole mastered set — and a word answered minutes ago with a
        23-day interval was as likely as one a month overdue. Prod: `desk`
        (interval 23 d) came back three times inside 24 hours; `spend` twice in
        six. The scheduler was computing intervals nobody read.

        Due-first also carries the old "show weak words more" intent without the
        randomness: a lapse shortens a word's interval, so it simply comes due
        sooner. Nothing due → None, and the push moves on to another stream.
        Takes a few rows so `exclude_uw_id` (the card just answered) can be
        skipped."""
        now = now or datetime.now(timezone.utc)
        q = (
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                UserWord.archived.is_(False),
                UserWord.status == WordStatus.MASTERED.value,
                UserWord.next_review_at <= now,
                or_(UserWord.snooze_until.is_(None), UserWord.snooze_until <= now),
                Word.translation.isnot(None),
                Word.is_function_word.is_(False),
            )
            .order_by(UserWord.next_review_at.asc(), UserWord.mastery_score.asc())
            .limit(3)
        )
        rows = [(r[0], r[1]) for r in (await self.session.execute(q)).all()]
        return _pick_avoiding(rows, exclude_uw_id)

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
        the user doesn't own are absent. Archived words report the sentinel
        status ``"archived"`` (not a real WordStatus) so the course counts them
        as dealt-with — otherwise a word the user hid via «я знаю» stays owned +
        non-mastered forever and permanently occupies a buffer slot, eventually
        starving the whole pipeline. Used by the course to decide top-ups."""
        if not word_ids:
            return {}
        q = select(UserWord.word_id, UserWord.status, UserWord.archived).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.word_id.in_(word_ids),
        )
        return {
            int(r[0]): ("archived" if r[2] else str(r[1]))
            for r in (await self.session.execute(q)).all()
        }

    async def count_new(self, user_id: int, track: LearningTrack) -> int:
        """Not-yet-started words still in rotation (status NEW, not archived)."""
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status == WordStatus.NEW.value,
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_archived(self, user_id: int, track: LearningTrack) -> int:
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(True),
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_snoozed(
        self, user_id: int, track: LearningTrack, now: datetime | None = None
    ) -> int:
        """Active words temporarily parked (snoozed leeches) — out of rotation
        but not archived. Counted separately so the progress breakdown
        (new + learning + mastered + snoozed + archived) sums to the total."""
        now = now or datetime.now(timezone.utc)
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
            UserWord.status.in_([WordStatus.LEARNING.value, WordStatus.REVIEW.value]),
            UserWord.snooze_until.isnot(None),
            UserWord.snooze_until > now,
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_weak(self, user_id: int, track: LearningTrack) -> int:
        """Words with mistakes still in active rotation — matches what the «weak»
        drill scope actually serves (not mastered, not archived), so the 🩹
        counter can't promise more than the drill can show."""
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.mistakes_count > 0,
            UserWord.status != WordStatus.MASTERED.value,
            UserWord.archived.is_(False),
        )
        return (await self.session.execute(q)).scalar_one()

    async def count_status(self, user_id: int, track: LearningTrack, status: WordStatus) -> int:
        """Count words in a status, excluding archived (archived words are shown
        only under their own bucket, so the progress breakdown doesn't double-count)."""
        q = select(func.count(UserWord.id)).where(
            UserWord.user_id == user_id,
            UserWord.track == track.value,
            UserWord.archived.is_(False),
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
        - SHAPE first: a negation answer («не имею») is quizzed against other
          negations («не делаю», «не могу»), not a random noun — otherwise the
          user picks "the only one with «не»" by elimination, learning nothing;
        - then the same part of speech / level (a verb against verbs);
        - a candidate that shares a meaning word with the correct answer is
          dropped, so we never offer a translation that's actually also correct
          (e.g. «держать» as a distractor when the answer is «хранить / держать»).
        """
        protected = _meaning_tokens_of(exclude_translations or [])
        seen: set[str] = {_norm(t) for t in (exclude_translations or []) if t}
        correct_neg = any(_is_negation(t) for t in (exclude_translations or []) if t)
        correct_shown = strip_latin_hints(
            next((t for t in (exclude_translations or []) if t), "")
        )
        correct_sig = _shape_signature(correct_shown)
        correct_len_bucket = min(len(correct_shown) // 8, 4)

        def tier(shown: str, pos: str | None, level: str | None) -> tuple[int, int, int, int, int]:
            neg_match = _is_negation(shown) == correct_neg
            pos_match = correct_pos is not None and pos == correct_pos
            level_match = correct_level is not None and level == correct_level
            # Without a known answer there is no shape to blend into — keep the
            # visual dimensions neutral so own-vocab candidates stay first.
            if correct_shown:
                shape_diff = _shape_distance(_shape_signature(shown), correct_sig)
                len_diff = abs(min(len(shown) // 8, 4) - correct_len_bucket)
            else:
                shape_diff = len_diff = 0
            return (
                0 if neg_match else 1,
                shape_diff,
                0 if pos_match else 1,
                0 if level_match else 1,
                len_diff,
            )

        candidates: list[tuple[tuple[int, int, int, int, int], str]] = []

        def consider(rows: list) -> None:
            for translation, pos, level in rows:
                if not translation:
                    continue
                n = _norm(translation)
                if n in seen:
                    continue
                if _meaning_tokens(translation) & protected:
                    continue  # shares a meaning with the answer -> would be valid
                # Options must not leak English (e.g. «стал (прошедшее от become)»)
                # — and dedup on the cleaned form too.
                shown = strip_latin_hints(translation)
                if _norm(shown) in seen:
                    continue
                seen.add(n)
                seen.add(_norm(shown))
                candidates.append((tier(shown, pos, level), shown))

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
            .limit(limit * 10)  # over-fetch: shape-ranking needs a real pool to pick from
        )
        consider(list((await self.session.execute(own_q)).all()))

        # Reach for pack words when the user's own vocab can't fill the card with
        # enough SAME-SHAPE candidates (e.g. a negation answer but few owned
        # negations) — so a "не …" answer still gets "не …" distractors.
        def well_matched() -> int:
            # Negation agrees AND no visible-shape bit sets the answer apart.
            return sum(1 for (t, _) in candidates if t[0] == 0 and t[1] == 0)

        shape_matched = well_matched()
        if shape_matched < limit and correct_neg:
            # Negations are a handful in the whole corpus — a random sample
            # below almost never contains one (that WAS the bug: an «aren't»
            # card quizzed against «утюг»). Fetch them directly instead.
            neg_q = (
                select(Word.translation, Word.part_of_speech, Word.level)
                .join(PackWord, PackWord.word_id == Word.id)
                .join(Pack, Pack.id == PackWord.pack_id)
                .where(
                    Pack.track == track.value,
                    Pack.is_active.is_(True),
                    or_(Word.translation.ilike("не %"), Word.translation.ilike("ни %")),
                )
                .order_by(func.random())
                .limit(limit * 4)
            )
            consider(list((await self.session.execute(neg_q)).all()))
            shape_matched = well_matched()
        if shape_matched < limit:
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
                .limit(limit * 16)
            )
            consider(list((await self.session.execute(pack_q)).all()))

        # Stable sort keeps own-before-pack and random order within a tier.
        candidates.sort(key=lambda c: c[0])
        return [translation for _, translation in candidates[:limit]]

    async def reverse_distractors(
        self,
        user_id: int,
        track: LearningTrack,
        exclude_word_id: int,
        limit: int = 3,
        correct_pos: str | None = None,
        correct_level: str | None = None,
    ) -> list[str]:
        """English writings to use as distractors on a REVERSE card (RU prompt →
        pick the English word). Mirror of quiz_distractors but returns the
        surface word, not the translation; own vocab first, then pack words on a
        cold start. Same part-of-speech / level rank so the options are plausible
        (a verb against verbs)."""
        seen: set[str] = set()
        candidates: list[tuple[tuple[int, int], str]] = []

        def tier(pos: str | None, level: str | None) -> tuple[int, int]:
            pos_match = correct_pos is not None and pos == correct_pos
            level_match = correct_level is not None and level == correct_level
            return (0 if pos_match else 1, 0 if level_match else 1)

        def consider(rows: list) -> None:
            for writing, pos, level in rows:
                if not writing:
                    continue
                n = _norm(writing)
                if n in seen:
                    continue
                seen.add(n)
                candidates.append((tier(pos, level), writing))

        own_q = (
            select(Word.writing, Word.part_of_speech, Word.level)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(
                UserWord.user_id == user_id,
                UserWord.track == track.value,
                Word.id != exclude_word_id,
            )
            .order_by(func.random())
            .limit(limit * 4)
        )
        consider(list((await self.session.execute(own_q)).all()))

        if len(candidates) < limit:
            pack_q = (
                select(Word.writing, Word.part_of_speech, Word.level)
                .join(PackWord, PackWord.word_id == Word.id)
                .join(Pack, Pack.id == PackWord.pack_id)
                .where(
                    Pack.track == track.value,
                    Pack.is_active.is_(True),
                    Word.id != exclude_word_id,
                )
                .order_by(func.random())
                .limit(limit * 8)
            )
            consider(list((await self.session.execute(pack_q)).all()))

        candidates.sort(key=lambda c: c[0])
        return [writing for _, writing in candidates[:limit]]
