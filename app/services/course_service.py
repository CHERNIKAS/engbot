from __future__ import annotations

import json
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.course import current_lesson, total_lessons, words_to_add
from app.domain.enums import LearningTrack, WordSource, WordStatus
from app.domain.pacing import ceiling_of, pace_of
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.grammar import GrammarRepository
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_tracks import UserTrackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.category_service import CategoryService, CategoryServiceError
from app.services.user_track_service import UserTrackService

COURSE_CATEGORY_NAME = "🎓 Курс"
_SPINE_KEY = "course:spine:{track}"
_SPINE_TTL = 21_600  # 6h — spine only changes on a content migration


@dataclass
class CourseProgress:
    enrolled: bool
    total_words: int
    mastered_words: int
    in_progress: int
    current_lesson: int
    total_lessons: int
    level: str
    finished: bool


async def course_progress_or_none(
    session: AsyncSession, redis: Redis, user: User, active_tracks: list[UserTrack]
) -> CourseProgress | None:
    """CourseProgress for the 📊 card — None unless the user has an English
    track and is enrolled (the course is EN-only)."""
    en = next(
        (ut for ut in active_tracks if ut.track == LearningTrack.ENGLISH.value), None
    )
    if en is None or not CourseService.is_enrolled(en):
        return None
    return await CourseService(session, redis).progress(user, en, LearningTrack.ENGLISH)


class CourseService:
    """The guided course: an ordered A1→A2→B1→B2 spine the bot auto-feeds into
    the user's vocabulary so the all-day push delivers it in order, choice-only.
    Enrollment is a flag in user_track.settings; progress is derived from mastery.
    """

    LEVELS: list[tuple[str, str]] = [
        ("level_a1", "A1"),
        ("level_a2", "A2"),
        ("level_b1", "B1"),
        ("level_b2", "B2"),
    ]

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._packs = PackRepository(session)
        self._uw = UserWordRepository(session)
        self._cats = CategoryRepository(session)

    @staticmethod
    def is_enrolled(user_track: UserTrack) -> bool:
        return bool((user_track.settings or {}).get("course_enrolled"))

    async def _spine(self, track: LearningTrack) -> list[tuple[int, str]]:
        key = _SPINE_KEY.format(track=track.value)
        cached = await self._redis.get(key)
        if cached:
            try:
                return [(int(a), str(b)) for a, b in json.loads(cached)]
            except (ValueError, TypeError):
                pass
        out: list[tuple[int, str]] = []
        for slug, label in self.LEVELS:
            pack = await self._packs.get_by_slug(slug)
            if pack is None:
                continue
            for wid in await self._packs.get_pack_word_ids(pack.id):
                out.append((wid, label))
        await self._redis.set(key, json.dumps(out, ensure_ascii=False), ex=_SPINE_TTL)
        return out

    async def _ensure_category(self, user_id: int, track: LearningTrack) -> int | None:
        cat = await self._cats.get_by_name(user_id, track, COURSE_CATEGORY_NAME)
        if cat is None:
            try:
                cat = await CategoryService(self._cats).create(user_id, track, COURSE_CATEGORY_NAME)
            except CategoryServiceError:
                cat = await self._cats.get_by_name(user_id, track, COURSE_CATEGORY_NAME)
        return cat.id if cat else None

    async def _set_enrolled(self, user: User, user_track: UserTrack, track: LearningTrack, value: bool) -> None:
        await UserTrackService(UserTrackRepository(self._session)).update_settings(
            user.id, track, {"course_enrolled": value}
        )
        # Keep the in-memory row consistent for the rest of this request.
        user_track.settings = {**(user_track.settings or {}), "course_enrolled": value}

    async def enroll(self, user: User, user_track: UserTrack, track: LearningTrack) -> int:
        await self._set_enrolled(user, user_track, track, True)
        return await self.refill(user, user_track, track)

    async def pause(self, user: User, user_track: UserTrack, track: LearningTrack) -> None:
        await self._set_enrolled(user, user_track, track, False)

    async def refill(self, user: User, user_track: UserTrack, track: LearningTrack) -> int:
        """Keep a buffer of in-progress course words by pulling the next spine
        words, up to the active-pool ceiling (pace × 3). The push then introduces
        them at `pace`/day. Idempotent / self-correcting."""
        if not self.is_enrolled(user_track):
            return 0
        spine = await self._spine(track)
        if not spine:
            return 0
        ids = [w for w, _ in spine]
        owned = await self._uw.status_map(user.id, track, ids)
        buffer_target = ceiling_of(pace_of(user_track.settings))
        to_add = words_to_add(ids, owned, buffer_target)
        added = 0
        if to_add:
            cat_id = await self._ensure_category(user.id, track)
            added = await self._uw.bulk_add(user.id, track, to_add, cat_id, WordSource.COURSE)
        await self._refill_grammar(user.id, track)
        return added

    async def _refill_grammar(self, user_id: int, track: LearningTrack) -> None:
        """Keep one grammar topic in progress at a time: when the current topic
        is fully mastered (or none yet), introduce the next one. Its rule card +
        exercises are then delivered by the push worker."""
        gr = GrammarRepository(self._session)
        if await gr.active_topic(user_id, track) is not None:
            return
        nxt = await gr.next_unstarted_topic(user_id, track)
        if nxt is not None:
            await gr.introduce_topic(user_id, nxt.id)

    async def level_map(
        self, user: User, track: LearningTrack
    ) -> list[tuple[str, int, int, int]]:
        """Per-level breakdown for the course map: (label, total, mastered,
        in_progress) in spine order."""
        spine = await self._spine(track)
        owned = await self._uw.status_map(user.id, track, [w for w, _ in spine])
        acc: dict[str, list[int]] = {}
        for wid, label in spine:
            total, mastered, in_progress = acc.setdefault(label, [0, 0, 0])
            status = owned.get(wid)
            acc[label][0] = total + 1
            if status == WordStatus.MASTERED.value:
                acc[label][1] = mastered + 1
            elif status is not None:
                acc[label][2] = in_progress + 1
        return [
            (label, *acc[label])
            for _, label in self.LEVELS
            if label in acc
        ]

    async def progress(self, user: User, user_track: UserTrack, track: LearningTrack) -> CourseProgress:
        spine = await self._spine(track)
        ids = [w for w, _ in spine]
        total = len(ids)
        owned = await self._uw.status_map(user.id, track, ids)
        mastered = sum(1 for w in ids if owned.get(w) == WordStatus.MASTERED.value)
        in_progress = sum(
            1 for w in ids if owned.get(w) and owned.get(w) != WordStatus.MASTERED.value
        )
        pos = min(mastered, max(0, total - 1))
        return CourseProgress(
            enrolled=self.is_enrolled(user_track),
            total_words=total,
            mastered_words=mastered,
            in_progress=in_progress,
            current_lesson=current_lesson(mastered, total),
            total_lessons=total_lessons(total),
            level=spine[pos][1] if spine else "—",
            finished=total > 0 and mastered >= total,
        )
