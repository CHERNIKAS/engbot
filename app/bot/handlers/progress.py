from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import ProgressCB, PushCB
from app.bot.keyboards.progress import backlog_confirm_kb, managed_words_kb, progress_kb
from app.bot.texts import (
    BACKLOG_DONE,
    BACKLOG_NOTHING,
    BACKLOG_OFFER,
    MANAGED_EMPTY,
    MANAGED_RESTORED,
    MANAGED_TITLE,
    MANAGED_UNSNOOZED,
)
from app.domain.enums import LearningTrack, WordStatus
from app.domain.models import User
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.backlog_service import BacklogService
from app.services.course_service import course_progress_or_none
from app.services.progress_service import ProgressService, format_progress
from app.services.user_track_service import UserTrackService

router = Router(name="progress")
_TRACK = LearningTrack.ENGLISH


async def _progress_text(
    session: AsyncSession, redis: Redis, user: User, uts: UserTrackService
) -> str:
    progress = ProgressService(session)
    active = await uts.list_active(user.id)
    views = [
        await progress.track_view(
            user.id,
            LearningTrack(ut.track),
            await progress.typical_goal(user.id, LearningTrack(ut.track)),
            tz_name=user.timezone,
        )
        for ut in active
    ]
    course = await course_progress_or_none(session, redis, user, active)
    return format_progress(user.streak_days, views, course=course)


@router.callback_query(ProgressCB.filter(F.action == "open"))
async def on_progress_open(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    redis: Redis,
    user_track_service: UserTrackService,
) -> None:
    text = await _progress_text(session, redis, user, user_track_service)
    has_managed = await UserWordRepository(session).has_managed(user.id, _TRACK)
    offer = await BacklogService(session).offer(user.id, _TRACK)
    if query.message:
        await query.message.edit_text(
            text,
            reply_markup=progress_kb(has_managed, backlog=offer.count),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(ProgressCB.filter(F.action == "backlog"))
async def on_backlog_offer(query: CallbackQuery, user: User, session: AsyncSession) -> None:
    """Explain the oversized pool before touching anything."""
    offer = await BacklogService(session).offer(user.id, _TRACK)
    if not offer.worth_offering:
        await query.answer(BACKLOG_NOTHING, show_alert=True)
        return
    if query.message:
        await query.message.edit_text(
            BACKLOG_OFFER.format(active=offer.active, target=offer.target, count=offer.count),
            reply_markup=backlog_confirm_kb(offer.count),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(ProgressCB.filter(F.action == "park"))
async def on_backlog_park(query: CallbackQuery, user: User, session: AsyncSession) -> None:
    parked, left = await BacklogService(session).park(user.id, _TRACK)
    if not parked:
        await query.answer(BACKLOG_NOTHING, show_alert=True)
        return
    has_managed = await UserWordRepository(session).has_managed(user.id, _TRACK)
    if query.message:
        await query.message.edit_text(
            BACKLOG_DONE.format(count=parked, left=left),
            reply_markup=progress_kb(has_managed),
            parse_mode="HTML",
        )
    await query.answer()


async def _render_managed(query: CallbackQuery, user: User, session: AsyncSession) -> None:
    repo = UserWordRepository(session)
    archived = [(uw.id, w.writing) for uw, w in await repo.list_archived(user.id, _TRACK)]
    snoozed = [(uw.id, w.writing) for uw, w in await repo.list_snoozed(user.id, _TRACK)]
    if not archived and not snoozed:
        if query.message:
            await query.message.edit_text(MANAGED_EMPTY, reply_markup=progress_kb(False))
        return
    if query.message:
        await query.message.edit_text(
            MANAGED_TITLE, reply_markup=managed_words_kb(archived, snoozed), parse_mode="HTML"
        )


@router.callback_query(ProgressCB.filter(F.action == "managed"))
async def on_progress_managed(query: CallbackQuery, user: User, session: AsyncSession) -> None:
    await _render_managed(query, user, session)
    await query.answer()


@router.callback_query(PushCB.filter(F.action == "unarchive"))
async def on_unarchive(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession
) -> None:
    uw = await UserWordRepository(session).get(callback_data.uw_id)
    if uw is not None and uw.user_id == user.id:
        uw.archived = False
        uw.status = WordStatus.NEW.value
        uw.repetitions_count = 0
        uw.mastery_score = 0.0
        await session.flush()
    await _render_managed(query, user, session)
    await query.answer(MANAGED_RESTORED)


@router.callback_query(PushCB.filter(F.action == "unsnooze"))
async def on_unsnooze(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession
) -> None:
    uw = await UserWordRepository(session).get(callback_data.uw_id)
    if uw is not None and uw.user_id == user.id:
        uw.snooze_until = None
        await session.flush()
    await _render_managed(query, user, session)
    await query.answer(MANAGED_UNSNOOZED)
