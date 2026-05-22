from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import CourseCB
from app.bot.keyboards.course import course_paused_kb, course_progress_kb, course_start_kb
from app.bot.texts import (
    COURSE_FINISHED,
    COURSE_INTRO,
    COURSE_PAUSED,
    COURSE_PROGRESS,
    COURSE_STARTED,
)
from app.domain.enums import LearningTrack
from app.domain.models import User, UserTrack
from app.services.course_service import CourseProgress, CourseService
from app.services.interaction_state_service import InteractionStateService

router = Router(name="course")

_BAR_WIDTH = 10


def _bar(done: int, total: int) -> str:
    if total <= 0:
        return ""
    filled = max(0, min(_BAR_WIDTH, round(_BAR_WIDTH * done / total)))
    return "▓" * filled + "░" * (_BAR_WIDTH - filled)


def _progress_text(prog: CourseProgress) -> str:
    if prog.finished:
        return COURSE_FINISHED.format(total=prog.total_words)
    return COURSE_PROGRESS.format(
        level=prog.level,
        lesson=prog.current_lesson,
        total_lessons=prog.total_lessons,
        bar=_bar(prog.mastered_words, prog.total_words),
        mastered=prog.mastered_words,
        total=prog.total_words,
        in_progress=prog.in_progress,
    )


@router.callback_query(CourseCB.filter(F.action == "open"))
async def on_open(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    redis: Redis,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    prog = await CourseService(session, redis).progress(user, user_track, current_track)
    if not prog.enrolled:
        text, kb = COURSE_INTRO, course_start_kb()
    else:
        text, kb = _progress_text(prog), course_progress_kb(finished=prog.finished)
    if query.message:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await query.answer()


@router.callback_query(CourseCB.filter(F.action == "start"))
async def on_start(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    redis: Redis,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    svc = CourseService(session, redis)
    await svc.enroll(user, user_track, current_track)
    prog = await svc.progress(user, user_track, current_track)
    if query.message:
        await query.message.edit_text(
            f"{COURSE_STARTED}\n\n{_progress_text(prog)}",
            reply_markup=course_progress_kb(finished=prog.finished),
            parse_mode="HTML",
        )
    await query.answer("🚀")


@router.callback_query(CourseCB.filter(F.action == "pause"))
async def on_pause(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await CourseService(session, redis).pause(user, user_track, current_track)
    if query.message:
        await query.message.edit_text(COURSE_PAUSED, reply_markup=course_paused_kb())
    await query.answer("⏸")
