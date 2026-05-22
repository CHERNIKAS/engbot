from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import ProgressCB, PushCB
from app.bot.keyboards.progress import managed_words_kb, progress_kb
from app.bot.texts import (
    MANAGED_EMPTY,
    MANAGED_RESTORED,
    MANAGED_TITLE,
    MANAGED_UNSNOOZED,
    PROGRESS_TITLE,
)
from app.domain.enums import LearningTrack, TRACK_LABELS, WordStatus
from app.domain.models import User
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.progress_service import ProgressService
from app.services.user_track_service import UserTrackService

router = Router(name="progress")
_TRACK = LearningTrack.ENGLISH


async def _progress_text(session: AsyncSession, user: User, uts: UserTrackService) -> str:
    progress = ProgressService(session)
    active = await uts.list_active(user.id)
    lines = []
    for ut in active:
        track = LearningTrack(ut.track)
        view = await progress.track_view(user.id, track, ut.daily_goal_words, tz_name=user.timezone)
        lines.append(
            f"{TRACK_LABELS[track]}: <b>{view.studied_today}</b> / {view.daily_goal} | "
            f"📚 {view.total_words} • ✅ {view.mastered_words} • 🔥 {view.weak_words}"
        )
    return PROGRESS_TITLE.format(streak=user.streak_days, per_track="\n".join(lines) or "—")


@router.callback_query(ProgressCB.filter(F.action == "open"))
async def on_progress_open(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    user_track_service: UserTrackService,
) -> None:
    text = await _progress_text(session, user, user_track_service)
    has_managed = await UserWordRepository(session).has_managed(user.id, _TRACK)
    if query.message:
        await query.message.edit_text(text, reply_markup=progress_kb(has_managed), parse_mode="HTML")
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
