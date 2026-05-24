from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PushCB
from app.bot.keyboards.settings import push_window_kb
from app.bot.texts import PUSH_SCHEDULE_KEPT, PUSH_WINDOW_TITLE
from app.config import get_settings
from app.domain.models import User, UserTrack
from app.services.interaction_state_service import InteractionStateService
from app.services.push_service import PushService

router = Router(name="push")


@router.callback_query(PushCB.filter(F.action == "ans"))
async def on_push_answer(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_answer(
        user, user_track, callback_data.uw_id, callback_data.idx, query
    )


@router.callback_query(PushCB.filter(F.action == "know"))
async def on_push_know(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_remove(user, callback_data.uw_id, query, known=True)


@router.callback_query(PushCB.filter(F.action == "hide"))
async def on_push_hide(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_remove(user, callback_data.uw_id, query, known=False)


@router.callback_query(PushCB.filter(F.action == "snooze"))
async def on_push_snooze(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_snooze(user, callback_data.uw_id, callback_data.days, query)


@router.callback_query(PushCB.filter(F.action == "rule"))
async def on_push_rule(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).show_rule(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "rule_ok"))
async def on_push_rule_ok(query: CallbackQuery) -> None:
    if query.message:
        try:
            await query.message.delete()
        except Exception:  # noqa: BLE001 — message gone / too old
            pass
    await query.answer("👍")


@router.callback_query(PushCB.filter(F.action == "keep_schedule"))
async def on_keep_schedule(query: CallbackQuery) -> None:
    if query.message:
        try:
            await query.message.edit_text(PUSH_SCHEDULE_KEPT)
        except Exception:  # noqa: BLE001
            pass
    await query.answer(PUSH_SCHEDULE_KEPT)


@router.callback_query(PushCB.filter(F.action == "open_window"))
async def on_open_window(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)  # so the SettingsCB hour buttons are allowed
    cfg = get_settings()
    s = user_track.settings or {}
    ws = int(s.get("push_ws", cfg.push_default_window_start))
    we = int(s.get("push_we", cfg.push_default_window_end))
    if query.message:
        await query.message.edit_text(PUSH_WINDOW_TITLE, reply_markup=push_window_kb(ws, we))
    await query.answer()
