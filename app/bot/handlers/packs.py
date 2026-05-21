from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import PacksCB
from app.bot.keyboards.packs import PACK_PAGE_SIZE, pack_browser_kb
from app.bot.states import InteractionState
from app.bot.texts import PACKS_ADDED_SUMMARY, PACKS_NONE_SELECTED, PACKS_TITLE
from app.domain.enums import LearningTrack
from app.domain.models import User
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.analytics import EVENT_PACK_ADDED, Analytics
from app.services.category_service import CategoryService, CategoryServiceError
from app.services.interaction_state_service import InteractionStateService
from app.services.pack_service import PackService

router = Router(name="packs")


def _selected(payload) -> set[int]:
    return {int(x) for x in (payload.data or {}).get("selected") or []}


async def _browser_view(
    user_id: int,
    track: LearningTrack,
    session: AsyncSession,
    page: int,
    selected: set[int],
) -> tuple[str, InlineKeyboardMarkup | None]:
    repo = PackRepository(session)
    packs = await repo.list_active(track)
    if not packs:
        return "Паков для этого трека пока нет.", None
    stats = await repo.stats_for_user(user_id, track)
    total_pages = max(1, (len(packs) + PACK_PAGE_SIZE - 1) // PACK_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_packs = packs[page * PACK_PAGE_SIZE : (page + 1) * PACK_PAGE_SIZE]
    return PACKS_TITLE, pack_browser_kb(page_packs, stats, selected, page, total_pages)


async def open_packs(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    """Entry point from the bottom menu (📦 Паки)."""
    await state_service.set(user.id, InteractionState.PACK_SELECTION, {"selected": []})
    text, kb = await _browser_view(user.id, current_track, session, 0, set())
    await message.answer(text, reply_markup=kb)


async def _rerender(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    page: int,
) -> None:
    payload = await state_service.get(user.id)
    selected = _selected(payload)
    text, kb = await _browser_view(user.id, current_track, session, page, selected)
    if query.message:
        await query.message.edit_text(text, reply_markup=kb)


@router.callback_query(PacksCB.filter(F.action == "menu"))
async def on_packs_menu(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.PACK_SELECTION, {"selected": []})
    await _rerender(query, user, current_track, session, state_service, 0)
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "toggle"))
async def on_toggle(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.PACK_SELECTION:
        await state_service.set(user.id, InteractionState.PACK_SELECTION, {"selected": []})
        payload = await state_service.get(user.id)
    selected = _selected(payload)
    pid = callback_data.pack_id
    if pid in selected:
        selected.discard(pid)
    else:
        selected.add(pid)
    await state_service.update_data(user.id, selected=list(selected))
    await _rerender(query, user, current_track, session, state_service, callback_data.page)
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "page"))
async def on_page(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await _rerender(query, user, current_track, session, state_service, callback_data.page)
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "reset"))
async def on_reset(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await state_service.update_data(user.id, selected=[])
    await _rerender(query, user, current_track, session, state_service, 0)
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "add"))
async def on_add(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    analytics: Analytics,
) -> None:
    payload = await state_service.get(user.id)
    selected = _selected(payload)
    if not selected:
        await query.answer(PACKS_NONE_SELECTED, show_alert=True)
        return

    pack_repo = PackRepository(session)
    cat_repo = CategoryRepository(session)
    cat_service = CategoryService(cat_repo)
    pack_service = PackService(pack_repo, UserWordRepository(session))

    total_added = 0
    packs_done = 0
    for pid in selected:
        pack = await pack_repo.get(pid)
        if pack is None:
            continue
        try:
            track = LearningTrack(pack.track)
        except ValueError:
            track = current_track
        # Each pack becomes its own folder in «Мои слова».
        category = await cat_repo.get_by_name(user.id, track, pack.title)
        if category is None:
            try:
                category = await cat_service.create(user.id, track, pack.title)
            except CategoryServiceError:
                category = await cat_repo.get_by_name(user.id, track, pack.title)
        category_id = category.id if category else None
        result = await pack_service.add_pack(user.id, track, pid, category_id)
        total_added += result.added
        packs_done += 1
        await analytics.emit(
            EVENT_PACK_ADDED,
            user_id=user.id,
            track=track.value,
            pack_id=pid,
            added=result.added,
        )

    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            PACKS_ADDED_SUMMARY.format(added=total_added, packs=packs_done),
            reply_markup=None,
        )
    await query.answer()
