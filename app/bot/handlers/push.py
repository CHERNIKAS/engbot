from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PushCB
from app.domain.models import User, UserTrack
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


@router.callback_query(PushCB.filter(F.action == "master"))
async def on_push_master(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_master(user, user_track, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "giveup"))
async def on_push_giveup(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_giveup(user, user_track, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "leech_park"))
async def on_push_leech_park(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_leech_park(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "leech_keep"))
async def on_push_leech_keep(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_leech_keep(user, callback_data.uw_id, query)


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
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:  # noqa: BLE001
                pass
    await query.answer("👍")


