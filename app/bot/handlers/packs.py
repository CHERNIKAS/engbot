from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import CategoryCB, PacksCB
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.packs import (
    pack_add_category_kb,
    pack_categories_kb,
    pack_list_kb,
    pack_preview_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    PACKS_LIST_TITLE,
    PACKS_PICK_CATEGORIES,
    PACK_ADDED,
    PACK_ALREADY_ADDED,
    PACK_PREVIEW,
)
from app.domain.enums import LearningTrack
from app.domain.models import User
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.packs import PackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.analytics import EVENT_PACK_ADDED, Analytics
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.pack_service import PackService
from app.services.user_track_service import UserTrackService

router = Router(name="packs")


def _selected(payload) -> set[str]:
    return set((payload.data or {}).get("selected") or [])


@router.callback_query(PacksCB.filter(F.action == "menu"))
async def on_packs_menu(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    categories = await PackRepository(session).list_categories(current_track)
    await state_service.set(user.id, InteractionState.PACK_SELECTION, {"selected": []})
    if query.message:
        await query.message.edit_text(
            PACKS_PICK_CATEGORIES,
            reply_markup=pack_categories_kb(categories, set()),
        )
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "toggle_cat"))
async def on_toggle_cat(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.PACK_SELECTION:
        await query.answer()
        return
    selected = _selected(payload)
    cat = callback_data.category
    if cat in selected:
        selected.remove(cat)
    else:
        selected.add(cat)
    await state_service.update_data(user.id, selected=list(selected))
    categories = await PackRepository(session).list_categories(current_track)
    if query.message:
        await query.message.edit_reply_markup(
            reply_markup=pack_categories_kb(categories, selected)
        )
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "reset_cats"))
async def on_reset_cats(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await state_service.update_data(user.id, selected=[])
    categories = await PackRepository(session).list_categories(current_track)
    if query.message:
        await query.message.edit_reply_markup(reply_markup=pack_categories_kb(categories, set()))
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "list"))
async def on_list(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    selected = list(_selected(payload))
    packs = await PackRepository(session).list_by_categories(current_track, selected)
    if not packs:
        await query.answer("Нет паков по выбранным категориям.", show_alert=True)
        return
    if query.message:
        await query.message.edit_text(PACKS_LIST_TITLE, reply_markup=pack_list_kb(packs))
    await query.answer()


@router.callback_query(PacksCB.filter(F.action == "preview"))
async def on_preview(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    session: AsyncSession,
) -> None:
    pack = await PackRepository(session).get(callback_data.pack_id)
    if pack is None:
        await query.answer("Не найдено.")
        return
    text = PACK_PREVIEW.format(
        title=pack.title,
        description=pack.description or "",
        count=pack.words_count,
    )
    if query.message:
        await query.message.edit_text(text, reply_markup=pack_preview_kb(pack.id), parse_mode="HTML")
    await query.answer()


CATEGORY_PICK_KIND = "cat_pick"


@router.callback_query(PacksCB.filter(F.action == "add"))
async def on_add_pack(
    query: CallbackQuery,
    callback_data: PacksCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    pack = await PackRepository(session).get(callback_data.pack_id)
    if pack is None:
        await query.answer("Не найдено.")
        return
    categories = await CategoryService(CategoryRepository(session)).list_user_categories(
        user.id, current_track
    )
    await state_service.update_data(user.id, pending_pack_id=callback_data.pack_id)
    version = await screen_service.bump(user.id, CATEGORY_PICK_KIND)
    if query.message:
        await query.message.edit_text(
            f"Куда сохранить «{pack.title}»?",
            reply_markup=pack_add_category_kb(pack.id, categories, version=version),
        )
    await query.answer()


@router.callback_query(CategoryCB.filter((F.action == "pick") & (F.flow == "pk")))
async def on_pick_category_for_pack(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
    analytics: Analytics,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, CATEGORY_PICK_KIND, callback_data.v):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return
    payload = await state_service.get(user.id)
    pack_id = (payload.data or {}).get("pending_pack_id")
    if not pack_id:
        await query.answer()
        return

    pack = await PackRepository(session).get(int(pack_id))
    if pack is None:
        await query.answer("Не найдено.")
        return

    # Use the pack's track, not the current_track — pack defines its track.
    try:
        track = LearningTrack(pack.track)
    except ValueError:
        track = current_track

    service = PackService(PackRepository(session), UserWordRepository(session))
    category_id = callback_data.category_id or None
    result = await service.add_pack(
        user_id=user.id, track=track, pack_id=int(pack_id), category_id=category_id
    )
    await analytics.emit(
        EVENT_PACK_ADDED,
        user_id=user.id,
        track=track.value,
        pack_id=int(pack_id),
        added=result.added,
    )
    await state_service.clear(user.id)

    active = await user_track_service.list_active(user.id)
    text = PACK_ADDED.format(count=result.added) if result.added > 0 else PACK_ALREADY_ADDED
    if query.message:
        await query.message.edit_text(text, reply_markup=main_menu_kb(active, current_track))
    await query.answer()
