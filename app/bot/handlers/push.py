from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PushCB
from app.domain.models import User, UserTrack
from app.services.push_service import PushService

router = Router(name="push")


@router.callback_query(PushCB.filter(F.action == "here"))
async def on_lesson_here(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis, query.bot).handle_lesson_here(user, query)


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
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    """Legacy callback for «Я это знаю».

    No keyboard emits `know` any more — it and `master` were two names for the
    same behaviour once this one started crediting the word instead of archiving
    it. Cards already sitting in people's chats still carry it, so it stays and
    routes to the same place.
    """
    await PushService(session, redis).handle_master(user, user_track, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "hide"))
async def on_push_hide(
    query: CallbackQuery, callback_data: PushCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    await PushService(session, redis).handle_remove(user, callback_data.uw_id, query)


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




@router.callback_query(PushCB.filter(F.action == "slot"))
async def on_constructor_slot(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_slot(
        user, callback_data.uw_id, callback_data.idx, query
    )


@router.callback_query(PushCB.filter(F.action == "pundo"))
async def on_constructor_undo(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_constructor_undo(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "phint"))
async def on_constructor_hint(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_constructor_hint(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "prule"))
async def on_constructor_rule(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_constructor_rule(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "pgiveup"))
async def on_constructor_giveup(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_constructor_giveup(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "trg"))
async def on_triage_toggle(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_triage_toggle(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "trgok"))
async def on_triage_done(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_triage_done(user, user_track, query)


@router.callback_query(PushCB.filter(F.action == "tstart"))
async def on_test_start(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_test_start(user, callback_data.uw_id, query)


@router.callback_query(PushCB.filter(F.action == "tlater"))
async def on_test_later(
    query: CallbackQuery,
    callback_data: PushCB,
    user: User,
    session: AsyncSession,
    redis: Redis,
) -> None:
    await PushService(session, redis).handle_test_later(user, callback_data.uw_id, query)
