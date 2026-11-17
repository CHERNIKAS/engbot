from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TRACK_LABELS, LearningTrack, WordStatus
from app.domain.models import GrammarReview, User, WordReview
from app.domain.levels import (
    LEVEL_B1_BAND1,
    LEVEL_FROM_BAND1,
    LEVEL_FROM_BAND2,
    STAGE_CHOOSE,
    STAGE_RECOGNIZE,
    STAGE_WRITE,
    level_from_coverage,
    word_stage,
)
from app.infrastructure.repositories.day_plans import DayPlanRepository
from app.infrastructure.repositories.grammar import GrammarRepository
from app.infrastructure.repositories.reviews import WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository

if TYPE_CHECKING:
    from app.services.course_service import CourseProgress




@dataclass
class TrackProgress:
    track: LearningTrack
    total_words: int
    new_words: int              # not started, in rotation
    learning_words: int         # actively learning (learning + review)
    mastered_words: int
    snoozed_words: int          # active but temporarily parked (snoozed leech)
    archived_words: int
    grammar_topics_total: int
    grammar_topics_done: int
    # The words in work, by the card they get now (see `word_stage`). Sums to
    # `learning_words` — it is the same set, split by step.
    stage_recognize: int = 0
    stage_choose: int = 0
    stage_write: int = 0
    # Today's plan: None when there is none in flight and none closed today.
    plan_done: int | None = None
    plan_total: int | None = None
    # The level as the frequency bands give it, and the way to the next one.
    level: str = "A1"
    band1_mastered: int = 0
    band2_mastered: int = 0


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


STAGE_LEGEND = "Каждое слово идёт по шагам:\n👀 узнаёшь → 👆 выбираешь → ✍️ пишешь сам → ⭐ выучено"


def _level_lines(t: TrackProgress) -> str:
    """«На каком лвле и сколько до следующего» — the thresholds are the ones
    `level_from_coverage` uses, so the bar fills exactly as the level moves."""
    head = f"🎓 Уровень {t.level}"
    if t.level == "A1":
        need = LEVEL_FROM_BAND1
        return (
            f"{head}\nДо A2: {t.band1_mastered} из {need} частых слов\n"
            f"{_bar(t.band1_mastered, need)}"
        )
    if t.level == "A2":
        return (
            f"{head}\nДо B1: {t.band1_mastered} из {LEVEL_B1_BAND1} частых слов"
            f" и {t.band2_mastered} из {LEVEL_FROM_BAND2} следующих\n"
            f"{_bar(t.band1_mastered + t.band2_mastered, LEVEL_B1_BAND1 + LEVEL_FROM_BAND2)}"
        )
    return head


def format_progress(
    streak_days: int,
    tracks: list[TrackProgress],
    course: "CourseProgress | None" = None,
) -> str:
    """Render the 📊 Прогресс card (pure, so it's unit-testable).

    Rewritten 2026-11-16 after a learner forwarded the old one asking what any
    of it meant: «Сегодня 2 / 4» was a self-measured daily bar unrelated to the
    plan, «учу: 31» hid that fourteen of those words were already at the typing
    step (so typed cards seemed to come from nowhere), and the level was not
    shown at all. Now: the plan, the words split by step, the level with the
    distance to the next, and one line saying how a word moves.
    """
    head = (
        "🌸 <b>Твой прогресс</b>\n"
        f"🔥 <b>{streak_days}</b> {_plural(streak_days, 'день', 'дня', 'дней')} подряд"
    )
    if not tracks:
        return head + "\n\nПока пусто — начни учить, и тут появится статистика 🌱"

    blocks: list[str] = []
    for t in tracks:
        parts: list[str] = []
        if len(tracks) > 1:
            parts.append(TRACK_LABELS[t.track])
        if t.plan_total:
            done = min(t.plan_done or 0, t.plan_total)
            title = "✅ План на сегодня пройден" if done >= t.plan_total else "📅 План на сегодня"
            parts.append(f"{title}: <b>{done}</b> из {t.plan_total}\n{_bar(done, t.plan_total)}")
        words = (
            "📚 <b>Слова</b>\n"
            f"⭐ выучено — {t.mastered_words}\n"
            f"✍️ пишешь сам — {t.stage_write}\n"
            f"👆 выбираешь из вариантов — {t.stage_choose}\n"
            f"👀 узнаёшь — {t.stage_recognize}\n"
            f"🆕 ещё впереди — {t.new_words}"
        )
        if t.snoozed_words:
            words += f"\n😴 отложено — {t.snoozed_words}"
        if t.archived_words:
            words += f"\n💤 в архиве — {t.archived_words}"
        parts.append(words)
        if t.track == LearningTrack.ENGLISH:
            parts.append(_level_lines(t))
        parts.append(
            f"📖 Грамматика: {t.grammar_topics_done} из {t.grammar_topics_total} "
            f"{_plural(t.grammar_topics_total, 'темы', 'тем', 'тем')}"
        )
        if course is not None and course.enrolled and t.track == LearningTrack.ENGLISH:
            if course.finished:
                parts.append("🎓 Курс: <b>пройден</b> 🎉")
            else:
                parts.append(
                    f"🎓 Курс: урок <b>{course.current_lesson}</b> / {course.total_lessons}"
                    f" · ⭐ {course.mastered_words}/{course.total_words}"
                )
        blocks.append("\n\n".join(parts))
    return head + "\n\n" + "\n\n".join(blocks) + "\n\n" + STAGE_LEGEND


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
        self._plans = DayPlanRepository(session)

    async def track_view(
        self,
        user: User,
        track: LearningTrack,
        *,
        today: date | None = None,
    ) -> TrackProgress:
        uid = user.id
        total = await self._user_words.total_for_user(uid, track)
        new = await self._user_words.count_new(uid, track)
        learning = await self._user_words.count_active(uid, track)
        mastered = await self._user_words.count_status(uid, track, WordStatus.MASTERED)
        snoozed = await self._user_words.count_snoozed(uid, track)
        archived = await self._user_words.count_archived(uid, track)
        g = await self._grammar.progress_counts(uid, track)
        stages = {STAGE_RECOGNIZE: 0, STAGE_CHOOSE: 0, STAGE_WRITE: 0}
        for reps, word_level in await self._user_words.active_reps_and_levels(uid, track):
            stages[word_stage(reps, word_level, user.level)] += 1
        band1, band2, _t1, _t2 = await self._user_words.band_coverage(uid, track)
        plan_done = plan_total = None
        plan = await self._plans.latest(uid, track)
        today = today or _local_today(user.timezone)
        if plan is not None and (
            plan.closed_at is None
            or plan.closed_at.astimezone(_resolve_tz(user.timezone)).date() == today
        ):
            items = plan.items or []
            plan_total = len(items)
            plan_done = sum(1 for i in items if i.get("done"))
        return TrackProgress(
            track=track,
            total_words=total,
            new_words=new,
            learning_words=learning,
            mastered_words=mastered,
            snoozed_words=snoozed,
            archived_words=archived,
            grammar_topics_total=g["topics_total"],
            grammar_topics_done=g["topics_done"],
            stage_recognize=stages[STAGE_RECOGNIZE],
            stage_choose=stages[STAGE_CHOOSE],
            stage_write=stages[STAGE_WRITE],
            plan_done=plan_done,
            plan_total=plan_total,
            level=level_from_coverage(band1, band2),
            band1_mastered=band1,
            band2_mastered=band2,
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
