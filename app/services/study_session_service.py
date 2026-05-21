from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.enums import (
    PACE_NEW_WORDS_PER_SESSION,
    LearningPace,
    LearningTrack,
    ReviewResult,
    StudyMode,
    StudyScope,
)
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.sessions import StudySessionRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.repetition_service import apply_review

SESSION_KEY = "session:{user_id}"


@dataclass
class StudyCardSnapshot:
    user_word_id: int
    word_id: int
    writing: str
    translation: str | None
    example: str | None
    # Japanese-friendly fields (None for English).
    kana: str | None = None
    romaji: str | None = None
    script_type: str | None = None
    level: str | None = None


@dataclass
class StudySessionSnapshot:
    session_id: int
    track: str
    mode: str
    scope: str
    scope_ref_id: int | None
    cards: list[dict]
    index: int = 0
    correct: int = 0
    wrong: int = 0
    quiz_options: dict[str, list[str]] = field(default_factory=dict)
    revealed: dict[str, bool] = field(default_factory=dict)


class StudySessionService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._user_words = UserWordRepository(session)
        self._sessions = StudySessionRepository(session)
        self._reviews = WordReviewRepository(session)
        self._ttl = get_settings().study_ttl_seconds

    def _key(self, user_id: int) -> str:
        return SESSION_KEY.format(user_id=user_id)

    async def get(self, user_id: int) -> StudySessionSnapshot | None:
        raw = await self._redis.get(self._key(user_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._redis.delete(self._key(user_id))
            return None
        return StudySessionSnapshot(**data)

    async def _save(self, user_id: int, snap: StudySessionSnapshot) -> None:
        await self._redis.set(
            self._key(user_id),
            json.dumps(asdict(snap), ensure_ascii=False),
            ex=self._ttl,
        )

    async def clear(self, user_id: int) -> None:
        await self._redis.delete(self._key(user_id))

    async def start(
        self,
        user: User,
        user_track: UserTrack,
        track: LearningTrack,
        mode: StudyMode,
        scope: StudyScope,
        scope_ref_id: int | None = None,
        studied_today: int = 0,
    ) -> StudySessionSnapshot | None:
        pace = LearningPace(user_track.learning_pace)
        new_cap = PACE_NEW_WORDS_PER_SESSION.get(pace, 6)

        if scope == StudyScope.QUICK:
            limit = max(5, user_track.daily_goal_words // 2)
        elif scope == StudyScope.GOAL:
            limit = max(1, user_track.daily_goal_words - studied_today)
        else:
            limit = max(user_track.daily_goal_words, 20)

        category_id = scope_ref_id if scope == StudyScope.CATEGORY else None

        rows = await self._user_words.pick_for_study(
            user_id=user.id,
            track=track,
            limit=limit,
            new_words_cap=new_cap,
            category_id=category_id,
            scope=scope.value,
        )
        if not rows:
            return None

        cards = [
            asdict(
                StudyCardSnapshot(
                    user_word_id=uw.id,
                    word_id=w.id,
                    writing=w.writing,
                    translation=uw.custom_translation or w.translation,
                    example=w.example_sentence,
                    kana=w.kana,
                    romaji=w.romaji,
                    script_type=w.script_type,
                    level=w.level,
                )
            )
            for uw, w in rows
        ]

        db_session = await self._sessions.create(
            user_id=user.id,
            track=track,
            mode=mode.value,
            scope=scope.value,
            scope_ref_id=scope_ref_id,
            words_total=len(cards),
        )

        quiz_options: dict[str, list[str]] = {}
        if mode == StudyMode.QUIZ:
            for uw, _w in rows:
                if not uw.custom_translation and not _w.translation:
                    continue
                correct = uw.custom_translation or _w.translation
                distractors = await self._user_words.quiz_distractors(
                    user.id,
                    track=track,
                    exclude_user_word_id=uw.id,
                    limit=3,
                    exclude_translations=[correct],
                )
                opts = [correct, *distractors[:3]]
                random.shuffle(opts)
                quiz_options[str(uw.id)] = opts

        snap = StudySessionSnapshot(
            session_id=db_session.id,
            track=track.value,
            mode=mode.value,
            scope=scope.value,
            scope_ref_id=scope_ref_id,
            cards=cards,
            quiz_options=quiz_options,
        )
        await self._save(user.id, snap)
        return snap

    async def current_card(self, user_id: int) -> StudyCardSnapshot | None:
        snap = await self.get(user_id)
        if snap is None:
            return None
        if snap.index >= len(snap.cards):
            return None
        return StudyCardSnapshot(**snap.cards[snap.index])

    async def reveal_translation(self, user_id: int) -> None:
        snap = await self.get(user_id)
        if snap is None:
            return
        snap.revealed[str(snap.index)] = True
        await self._save(user_id, snap)

    async def answer(
        self,
        user: User,
        user_track: UserTrack,
        result: ReviewResult,
    ) -> StudySessionSnapshot | None:
        snap = await self.get(user.id)
        if snap is None or snap.index >= len(snap.cards):
            return snap

        card = StudyCardSnapshot(**snap.cards[snap.index])
        track = LearningTrack(snap.track)

        user_word = await self._user_words.get(card.user_word_id)
        if user_word is not None:
            apply_review(user_word, result, LearningPace(user_track.learning_pace))
            await self._session.flush()

            await self._reviews.create(
                user_id=user.id,
                track=track,
                user_word_id=user_word.id,
                session_id=snap.session_id,
                result=result.value,
            )

        if result in (ReviewResult.EASY, ReviewResult.NORMAL, ReviewResult.CORRECT):
            snap.correct += 1
        else:
            snap.wrong += 1

        await self._sessions.increment_counters(
            snap.session_id,
            correct_delta=1 if result in (ReviewResult.EASY, ReviewResult.NORMAL, ReviewResult.CORRECT) else 0,
            wrong_delta=1 if result in (ReviewResult.HARD, ReviewResult.WRONG) else 0,
        )

        snap.index += 1
        await self._save(user.id, snap)
        return snap

    async def skip(self, user_id: int) -> StudySessionSnapshot | None:
        snap = await self.get(user_id)
        if snap is None or snap.index >= len(snap.cards):
            return snap
        snap.index += 1
        await self._save(user_id, snap)
        return snap

    async def delete_current(self, user_id: int) -> StudySessionSnapshot | None:
        snap = await self.get(user_id)
        if snap is None or snap.index >= len(snap.cards):
            return snap
        card = StudyCardSnapshot(**snap.cards[snap.index])
        await self._user_words.delete(card.user_word_id)
        snap.cards.pop(snap.index)
        if snap.session_id:
            db_session = await self._sessions.get(snap.session_id)
            if db_session is not None:
                db_session.words_total = max(0, db_session.words_total - 1)
                await self._session.flush()
        await self._save(user_id, snap)
        return snap

    async def finish(self, user_id: int) -> StudySessionSnapshot | None:
        snap = await self.get(user_id)
        if snap is None:
            return None
        await self._sessions.finish(snap.session_id, correct=snap.correct, wrong=snap.wrong)
        await self.clear(user_id)
        return snap

    def is_complete(self, snap: StudySessionSnapshot) -> bool:
        return snap.index >= len(snap.cards)
