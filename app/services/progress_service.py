from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TRACK_LABELS, LearningTrack, WordStatus
from app.domain.models import GrammarReview, User, WordReview
from app.infrastructure.repositories.grammar import GrammarRepository
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository

if TYPE_CHECKING:
    from app.services.course_service import CourseProgress


# Floor and fallback for the self-referential daily bar.
MIN_DAILY_GOAL = 3
DEFAULT_DAILY_GOAL = 6


@dataclass
class TrackProgress:
    track: LearningTrack
    studied_today: int          # answers today: words + grammar
    studied_today_words: int
    studied_today_grammar: int
    daily_goal: int
    total_words: int
    new_words: int              # not started, in rotation
    learning_words: int         # actively learning (learning + review)
    mastered_words: int
    weak_words: int             # answered wrong at least once
    snoozed_words: int          # active but temporarily parked (snoozed leech)
    archived_words: int
    grammar_topics_total: int
    grammar_topics_done: int
    grammar_items_mastered: int
    grammar_items_in_progress: int


@dataclass
class ProgressView:
    streak_days: int
    tracks: list[TrackProgress]


def _bar(done: int, goal: int, width: int = 10) -> str:
    """A 10-cell ▓/░ progress bar, capped at 100%."""
    if goal <= 0:
        filled = width
    else:
        filled = max(0, min(width, round(width * done / goal)))
    return "▓" * filled + "░" * (width - filled)


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Russian plural: 1 день / 2 дня / 5 дней."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def format_progress(
    streak_days: int,
    tracks: list[TrackProgress],
    course: "CourseProgress | None" = None,
) -> str:
    """Render the 📊 Прогресс card (pure, so it's unit-testable). `course` adds
    a course line to the English block when the user is enrolled."""
    head = (
        "🌸 <b>Твой прогресс</b>\n"
        f"🔥 Серия: <b>{streak_days}</b> {_plural(streak_days, 'день', 'дня', 'дней')} подряд"
    )
    if not tracks:
        return head + "\n\nПока пусто — начни учить, и тут появится статистика 🌱"

    blocks: list[str] = []
    for t in tracks:
        pct = 0 if t.daily_goal <= 0 else min(100, round(100 * t.studied_today / t.daily_goal))
        today_detail = f"🔤 слова: {t.studied_today_words} · 📖 грамматика: {t.studied_today_grammar}"
        block = (
            f"{TRACK_LABELS[t.track]}\n"
            f"🎯 Сегодня: <b>{t.studied_today}</b> / {t.daily_goal}  ({pct}%)\n"
            f"{_bar(t.studied_today, t.daily_goal)}\n"
            f"   {today_detail}\n\n"
            f"📚 Словарь — всего <b>{t.total_words}</b>\n"
            f"   🌱 учу: {t.learning_words} · ⭐ выучено: {t.mastered_words}\n"
            f"   🆕 новые: {t.new_words} · 🩹 с ошибками: {t.weak_words}"
        )
        if t.snoozed_words:
            block += f" · 😴 отложено: {t.snoozed_words}"
        if t.archived_words:
            block += f" · 💤 архив: {t.archived_words}"
        block += (
            f"\n\n📖 Грамматика — <b>{t.grammar_topics_done}</b> / {t.grammar_topics_total} "
            f"{_plural(t.grammar_topics_total, 'тема', 'темы', 'тем')}\n"
            f"   ⭐ упражнений: {t.grammar_items_mastered} · 🌱 в работе: {t.grammar_items_in_progress}"
        )
        if course is not None and course.enrolled and t.track == LearningTrack.ENGLISH:
            if course.finished:
                block += "\n\n🎓 Курс: <b>пройден</b> 🎉"
            else:
                block += (
                    f"\n\n🎓 Курс: урок <b>{course.current_lesson}</b> / {course.total_lessons}"
                    f" · {course.level} · ⭐ {course.mastered_words}/{course.total_words}"
                )
        blocks.append(block)
    return head + "\n\n" + "\n\n".join(blocks)


def _resolve_tz(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_today(tz_name: str | None) -> date:
    tz = _resolve_tz(tz_name)
    return datetime.now(tz).date()


def _day_utc_bounds(local_day: date, tz_name: str | None) -> tuple[datetime, datetime]:
    """Returns [start_utc, end_utc) representing one calendar day in the user's TZ."""
    tz = _resolve_tz(tz_name)
    start_local = datetime.combine(local_day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


class ProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_words = UserWordRepository(session)
        self._grammar = GrammarRepository(session)
        self._reviews = WordReviewRepository(session)

    async def typical_goal(self, user_id: int, track: LearningTrack) -> int:
        """The bar the progress line measures against: what this user manages on
        a normal day.

        Replaces the goal they picked once at signup. Prod showed that number
        was aspiration, not plan — the two users who chose 50 averaged 8.9 and
        3.9 answers a day and never came close, while everyone who chose 5
        cleared it comfortably. A target nobody meets stops being a target.
        Measuring someone against their own recent self is a bar they can
        actually move.
        """
        typical = await self._reviews.typical_daily_answers(user_id, track)
        return max(MIN_DAILY_GOAL, round(typical or DEFAULT_DAILY_GOAL))

    async def track_view(
        self,
        user_id: int,
        track: LearningTrack,
        daily_goal: int,
        *,
        tz_name: str = "UTC",
    ) -> TrackProgress:
        words_today = await self.studied_today_count(user_id, track, tz_name=tz_name)
        grammar_today = await self.grammar_studied_today_count(user_id, track, tz_name=tz_name)
        total = await self._user_words.total_for_user(user_id, track)
        new = await self._user_words.count_new(user_id, track)
        learning = await self._user_words.count_active(user_id, track)
        mastered = await self._user_words.count_status(user_id, track, WordStatus.MASTERED)
        weak = await self._user_words.count_weak(user_id, track)
        snoozed = await self._user_words.count_snoozed(user_id, track)
        archived = await self._user_words.count_archived(user_id, track)
        g = await self._grammar.progress_counts(user_id, track)
        return TrackProgress(
            track=track,
            studied_today=words_today + grammar_today,
            studied_today_words=words_today,
            studied_today_grammar=grammar_today,
            daily_goal=daily_goal,
            total_words=total,
            new_words=new,
            learning_words=learning,
            mastered_words=mastered,
            weak_words=weak,
            snoozed_words=snoozed,
            archived_words=archived,
            grammar_topics_total=g["topics_total"],
            grammar_topics_done=g["topics_done"],
            grammar_items_mastered=g["items_mastered"],
            grammar_items_in_progress=g["items_in_progress"],
        )

    async def studied_today_count(
        self,
        user_id: int,
        track: LearningTrack,
        *,
        tz_name: str = "UTC",
    ) -> int:
        today_local = _local_today(tz_name)
        start_utc, end_utc = _day_utc_bounds(today_local, tz_name)
        q = select(func.count(WordReview.id)).where(
            and_(
                WordReview.user_id == user_id,
                WordReview.track == track.value,
                WordReview.reviewed_at >= start_utc,
                WordReview.reviewed_at < end_utc,
            )
        )
        return (await self._session.execute(q)).scalar_one() or 0

    async def grammar_studied_today_count(
        self,
        user_id: int,
        track: LearningTrack,
        *,
        tz_name: str = "UTC",
    ) -> int:
        today_local = _local_today(tz_name)
        start_utc, end_utc = _day_utc_bounds(today_local, tz_name)
        q = select(func.count(GrammarReview.id)).where(
            and_(
                GrammarReview.user_id == user_id,
                GrammarReview.track == track.value,
                GrammarReview.reviewed_at >= start_utc,
                GrammarReview.reviewed_at < end_utc,
            )
        )
        return (await self._session.execute(q)).scalar_one() or 0

    async def update_streak(self, user: User) -> bool:
        """Global streak — shared across all tracks. Call when any track session finishes."""
        today_local = _local_today(user.timezone)
        if user.last_study_date == today_local:
            return False
        if user.last_study_date == today_local - timedelta(days=1):
            user.streak_days += 1
        else:
            user.streak_days = 1
        user.last_study_date = today_local
        await self._session.flush()
        return True
