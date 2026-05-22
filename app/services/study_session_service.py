from __future__ import annotations

import json
import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.enums import (
    PACE_NEW_WORDS_PER_SESSION,
    LearningPace,
    LearningTrack,
    ReviewResult,
    StudyScope,
)
from app.domain.models import User, UserTrack
from app.domain.study_drill import STAGE_QUIZ, DrillState
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.sessions import StudySessionRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.repetition_service import apply_review

SESSION_KEY = "session:{user_id}"


@dataclass
class CardView:
    uw_id: int
    stage: str
    writing: str
    translation: str | None
    example: str | None
    options: list[str]
    learned: int
    total: int
    kana: str | None = None
    romaji: str | None = None
    script_type: str | None = None


@dataclass
class FinishSummary:
    learned: int
    total: int
    mistakes: int


class StudySessionService:
    """Drill-based study: each word is cleared through QUIZ then TYPE, and wrong
    answers keep coming back until answered correctly. Spaced repetition is
    persisted once, on finish, from how many mistakes a word needed (mistakes →
    shorter interval → it returns sooner)."""

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._user_words = UserWordRepository(session)
        self._sessions = StudySessionRepository(session)
        self._reviews = WordReviewRepository(session)
        self._ttl = get_settings().study_ttl_seconds

    def _key(self, user_id: int) -> str:
        return SESSION_KEY.format(user_id=user_id)

    async def _get_raw(self, user_id: int) -> dict | None:
        raw = await self._redis.get(self._key(user_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            await self._redis.delete(self._key(user_id))
            return None

    async def _save_raw(self, user_id: int, snap: dict) -> None:
        await self._redis.set(
            self._key(user_id), json.dumps(snap, ensure_ascii=False), ex=self._ttl
        )

    async def clear(self, user_id: int) -> None:
        await self._redis.delete(self._key(user_id))

    async def start(
        self,
        user: User,
        user_track: UserTrack,
        track: LearningTrack,
        scope: StudyScope,
        scope_ref_id: int | None = None,
        studied_today: int = 0,
    ) -> CardView | None:
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
        # Only testable words (with a translation) can be quizzed/typed.
        rows = [(uw, w) for uw, w in rows if (uw.custom_translation or w.translation)]
        if not rows:
            return None

        cards: dict[str, dict] = {}
        quiz_options: dict[str, list[str]] = {}
        for uw, w in rows:
            correct = uw.custom_translation or w.translation
            cards[str(uw.id)] = {
                "writing": w.writing,
                "translation": correct,
                "example": w.example_sentence,
                "kana": w.kana,
                "romaji": w.romaji,
                "script_type": w.script_type,
            }
            distractors = await self._user_words.quiz_distractors(
                user.id,
                track=track,
                exclude_user_word_id=uw.id,
                limit=3,
                exclude_translations=[correct],
                correct_pos=w.part_of_speech,
                correct_level=w.level,
            )
            opts = [correct, *distractors[:3]]
            random.shuffle(opts)
            quiz_options[str(uw.id)] = opts

        db_session = await self._sessions.create(
            user_id=user.id,
            track=track,
            mode="learn",
            scope=scope.value,
            scope_ref_id=scope_ref_id,
            words_total=len(rows),
        )

        # Multi-word entries (phrases, phrasal verbs) are recognition-only:
        # cleared after QUIZ, no typing stage.
        quiz_only = [uw.id for uw, w in rows if " " in (w.writing or "").strip()]
        drill = DrillState.new([uw.id for uw, _ in rows], quiz_only=quiz_only)
        snap = {
            "session_id": db_session.id,
            "track": track.value,
            "scope": scope.value,
            "scope_ref_id": scope_ref_id,
            "cards": cards,
            "quiz_options": quiz_options,
            "drill": drill.to_dict(),
        }
        await self._save_raw(user.id, snap)
        return self._view(snap, drill)

    def _view(self, snap: dict, drill: DrillState) -> CardView | None:
        cur = drill.current()
        if cur is None:
            return None
        uw_id, stage = cur
        card = snap["cards"].get(str(uw_id))
        if card is None:
            return None
        options = snap["quiz_options"].get(str(uw_id), []) if stage == STAGE_QUIZ else []
        return CardView(
            uw_id=uw_id,
            stage=stage,
            writing=card["writing"],
            translation=card.get("translation"),
            example=card.get("example"),
            options=options,
            learned=drill.learned_count(),
            total=drill.total,
            kana=card.get("kana"),
            romaji=card.get("romaji"),
            script_type=card.get("script_type"),
        )

    async def current_view(self, user_id: int) -> CardView | None:
        snap = await self._get_raw(user_id)
        if snap is None:
            return None
        return self._view(snap, DrillState.from_dict(snap["drill"]))

    async def answer(self, user_id: int, correct: bool) -> CardView | None:
        snap = await self._get_raw(user_id)
        if snap is None:
            return None
        drill = DrillState.from_dict(snap["drill"])
        drill.answer(correct)
        snap["drill"] = drill.to_dict()
        await self._save_raw(user_id, snap)
        return self._view(snap, drill)

    async def skip(self, user_id: int) -> CardView | None:
        snap = await self._get_raw(user_id)
        if snap is None:
            return None
        drill = DrillState.from_dict(snap["drill"])
        drill.skip()
        snap["drill"] = drill.to_dict()
        await self._save_raw(user_id, snap)
        return self._view(snap, drill)

    async def delete_current(self, user_id: int) -> CardView | None:
        snap = await self._get_raw(user_id)
        if snap is None:
            return None
        drill = DrillState.from_dict(snap["drill"])
        cur = drill.current()
        if cur is not None:
            uw_id, _ = cur
            await self._user_words.delete(uw_id)
            drill.remove_current()
            snap["cards"].pop(str(uw_id), None)
            snap["quiz_options"].pop(str(uw_id), None)
        snap["drill"] = drill.to_dict()
        await self._save_raw(user_id, snap)
        return self._view(snap, drill)

    async def is_complete(self, user_id: int) -> bool:
        snap = await self._get_raw(user_id)
        if snap is None:
            return True
        return DrillState.from_dict(snap["drill"]).is_complete()

    async def finish(self, user: User, user_track: UserTrack) -> FinishSummary | None:
        snap = await self._get_raw(user.id)
        if snap is None:
            return None
        drill = DrillState.from_dict(snap["drill"])
        pace = LearningPace(user_track.learning_pace)
        track = LearningTrack(snap["track"])

        for uw_id in drill.learned:
            uw = await self._user_words.get(uw_id)
            if uw is None:
                continue
            m = drill.mistakes_for(uw_id)
            if m == 0:
                result = ReviewResult.NORMAL
            elif m <= 2:
                result = ReviewResult.HARD
            else:
                result = ReviewResult.WRONG
            apply_review(uw, result, pace)
            await self._reviews.create(
                user_id=user.id,
                track=track,
                user_word_id=uw.id,
                session_id=snap["session_id"],
                result=result.value,
            )
        await self._session.flush()

        mistakes_total = sum(int(v) for v in drill.mistakes.values())
        await self._sessions.finish(
            snap["session_id"], correct=drill.learned_count(), wrong=mistakes_total
        )
        await self.clear(user.id)
        return FinishSummary(
            learned=drill.learned_count(), total=drill.total, mistakes=mistakes_total
        )
