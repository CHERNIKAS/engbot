from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import CategoryCB
from app.bot.filters import InState
from app.bot.keyboards.add_words import add_choose_category_kb
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.keyboards.my_words import (
    categories_overview_kb,
    category_delete_confirm_kb,
    category_manage_kb,
    category_target_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_CHOOSE_CATEGORY,
    CATEGORY_CREATED,
    CATEGORY_DELETE_CONFIRM,
    CATEGORY_DELETED,
    CATEGORY_MANAGE_TITLE,
    CATEGORY_MERGE_PICK,
    CATEGORY_MERGED,
    CATEGORY_MOVE_PICK,
    CATEGORY_MOVED,
    CATEGORY_NEW_EMPTY,
    CATEGORY_NEW_EXISTS,
    CATEGORY_NEW_PROMPT,
    CATEGORY_NEW_TOO_LONG,
    CATEGORY_NO_TARGETS,
    CATEGORY_RENAME_PROMPT,
    CATEGORY_RENAMED,
    MAIN_MENU,
    MY_WORDS_EMPTY,
    STALE_CALLBACK,
)
from app.domain.enums import LearningTrack
from app.domain.models import User
from app.infrastructure.repositories.categories import CategoryRepository
from app.services.category_service import CategoryService, CategoryServiceError
from app.services.interaction_state_service import InteractionStateService
from app.services.user_track_service import UserTrackService

router = Router(name="categories")


@router.callback_query(CategoryCB.filter(F.action == "new"))
async def on_new_category(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    await state_service.set(
        user.id,
        InteractionState.WAITING_NEW_CATEGORY_NAME,
        {
            "return_flow": callback_data.flow,
            "previous_state": payload.state.value,
            "previous_data": payload.data,
        },
    )
    if query.message:
        await query.message.edit_text(CATEGORY_NEW_PROMPT, reply_markup=cancel_only_kb())
    await query.answer()


@router.message(InState(InteractionState.WAITING_NEW_CATEGORY_NAME), F.text)
async def on_new_category_text(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    screen_service,
    interaction_state,
) -> None:
    name = (message.text or "").strip()
    repo = CategoryRepository(session)
    service = CategoryService(repo)
    try:
        category = await service.create(user.id, current_track, name)
    except CategoryServiceError as exc:
        code = str(exc)
        await message.answer(
            {
                "empty": CATEGORY_NEW_EMPTY,
                "too_long": CATEGORY_NEW_TOO_LONG,
                "exists": CATEGORY_NEW_EXISTS,
            }.get(code, CATEGORY_NEW_EMPTY)
        )
        return

    previous_state_val = (interaction_state.data or {}).get("previous_state")
    previous_data = (interaction_state.data or {}).get("previous_data") or {}
    return_flow = (interaction_state.data or {}).get("return_flow") or "mw"

    if previous_state_val:
        try:
            previous_state = InteractionState(previous_state_val)
        except ValueError:
            previous_state = InteractionState.IDLE
    else:
        previous_state = InteractionState.IDLE

    await message.answer(CATEGORY_CREATED.format(name=category.name))

    if previous_state in (
        InteractionState.WAITING_CATEGORY_FOR_WORDS,
        InteractionState.WAITING_TXT_CATEGORY,
    ):
        await state_service.set(user.id, previous_state, previous_data)
        # Bump screen version so the fresh picker invalidates any stale buttons
        # from the picker shown before "➕ Новая категория" was clicked.
        version = await screen_service.bump(user.id, "cat_pick")
        categories = await service.list_user_categories(user.id, current_track)
        await message.answer(
            ADD_CHOOSE_CATEGORY,
            reply_markup=add_choose_category_kb(
                categories, flow=return_flow, version=version
            ),
        )
    else:
        await state_service.clear(user.id)
        await message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())


# --------------------------------------------------------------------------- #
# Category management: rename / delete / move / merge
# --------------------------------------------------------------------------- #

CAT_DEL_KIND = "cat_del"
CAT_MOVE_KIND = "cat_move"
CAT_MERGE_KIND = "cat_merge"

_RENAME_ERRORS = {
    "empty": CATEGORY_NEW_EMPTY,
    "too_long": CATEGORY_NEW_TOO_LONG,
    "exists": CATEGORY_NEW_EXISTS,
    "not_found": "Категория не найдена.",
}


async def _show_overview(
    query: CallbackQuery, user: User, current_track: LearningTrack, session: AsyncSession
) -> None:
    service = CategoryService(CategoryRepository(session))
    categories = await service.list_user_categories(user.id, current_track)
    counts = await service.counts(user.id, current_track)
    if not query.message:
        return
    if sum(counts.values()) == 0 and not categories:
        await query.message.edit_text(MY_WORDS_EMPTY, reply_markup=None)
    else:
        await query.message.edit_text(
            "📚 Мои слова",
            reply_markup=categories_overview_kb(categories, counts, flow="mw"),
        )


@router.callback_query(CategoryCB.filter(F.action == "manage"))
async def on_manage(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    service = CategoryService(CategoryRepository(session))
    cat = await service.get(callback_data.category_id)
    if cat is None:
        await query.answer("Категория не найдена.")
        return
    counts = await service.counts(user.id, current_track)
    if query.message:
        await query.message.edit_text(
            CATEGORY_MANAGE_TITLE.format(name=cat.name, count=counts.get(cat.id, 0)),
            reply_markup=category_manage_kb(cat.id),
        )
    await query.answer()


@router.callback_query(CategoryCB.filter(F.action == "rename"))
async def on_rename(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(
        user.id,
        InteractionState.WAITING_CATEGORY_RENAME,
        {"category_id": callback_data.category_id},
    )
    if query.message:
        await query.message.edit_text(CATEGORY_RENAME_PROMPT, reply_markup=cancel_only_kb())
    await query.answer()


@router.message(InState(InteractionState.WAITING_CATEGORY_RENAME), F.text)
async def on_rename_text(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    interaction_state,
) -> None:
    cid = (interaction_state.data or {}).get("category_id")
    if not cid:
        await state_service.clear(user.id)
        return
    service = CategoryService(CategoryRepository(session))
    try:
        cat = await service.rename(user.id, current_track, int(cid), message.text or "")
    except CategoryServiceError as exc:
        await message.answer(_RENAME_ERRORS.get(str(exc), CATEGORY_NEW_EMPTY))
        return
    await state_service.clear(user.id)
    counts = await service.counts(user.id, current_track)
    await message.answer(CATEGORY_RENAMED.format(name=cat.name))
    await message.answer(
        CATEGORY_MANAGE_TITLE.format(name=cat.name, count=counts.get(cat.id, 0)),
        reply_markup=category_manage_kb(cat.id),
    )


@router.callback_query(CategoryCB.filter(F.action == "del_ask"))
async def on_cat_delete_ask(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    session: AsyncSession,
    screen_service,
) -> None:
    service = CategoryService(CategoryRepository(session))
    cat = await service.get(callback_data.category_id)
    if cat is None:
        await query.answer("Категория не найдена.")
        return
    version = await screen_service.bump(user.id, CAT_DEL_KIND)
    if query.message:
        await query.message.edit_text(
            CATEGORY_DELETE_CONFIRM.format(name=cat.name),
            reply_markup=category_delete_confirm_kb(cat.id, version),
        )
    await query.answer()


@router.callback_query(CategoryCB.filter(F.action == "del_confirm"))
async def on_cat_delete_confirm(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, CAT_DEL_KIND, callback_data.v):
        await query.answer(STALE_CALLBACK)
        return
    await CategoryService(CategoryRepository(session)).delete(callback_data.category_id)
    await query.answer(CATEGORY_DELETED)
    await _show_overview(query, user, current_track, session)


@router.callback_query(CategoryCB.filter(F.action == "move"))
async def on_move(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    screen_service,
) -> None:
    service = CategoryService(CategoryRepository(session))
    cat = await service.get(callback_data.category_id)
    if cat is None:
        await query.answer("Категория не найдена.")
        return
    categories = await service.list_user_categories(user.id, current_track)
    version = await screen_service.bump(user.id, CAT_MOVE_KIND)
    if query.message:
        await query.message.edit_text(
            CATEGORY_MOVE_PICK.format(name=cat.name),
            reply_markup=category_target_kb(
                cat.id, categories, "move", version, include_uncategorized=True
            ),
        )
    await query.answer()


@router.callback_query(CategoryCB.filter(F.action == "merge"))
async def on_merge(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    screen_service,
) -> None:
    service = CategoryService(CategoryRepository(session))
    cat = await service.get(callback_data.category_id)
    if cat is None:
        await query.answer("Категория не найдена.")
        return
    others = [c for c in await service.list_user_categories(user.id, current_track) if c.id != cat.id]
    if not others:
        await query.answer(CATEGORY_NO_TARGETS, show_alert=True)
        return
    version = await screen_service.bump(user.id, CAT_MERGE_KIND)
    if query.message:
        await query.message.edit_text(
            CATEGORY_MERGE_PICK.format(name=cat.name),
            reply_markup=category_target_kb(
                cat.id, others, "merge", version, include_uncategorized=False
            ),
        )
    await query.answer()


@router.callback_query(CategoryCB.filter(F.action == "move_to"))
async def on_move_to(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, CAT_MOVE_KIND, callback_data.v):
        await query.answer(STALE_CALLBACK)
        return
    target = None if callback_data.target_id == -1 else callback_data.target_id
    moved = await CategoryService(CategoryRepository(session)).move_words(
        user.id, current_track, callback_data.category_id, target
    )
    await query.answer(CATEGORY_MOVED.format(count=moved))
    await _show_overview(query, user, current_track, session)


@router.callback_query(CategoryCB.filter(F.action == "merge_to"))
async def on_merge_to(
    query: CallbackQuery,
    callback_data: CategoryCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, CAT_MERGE_KIND, callback_data.v):
        await query.answer(STALE_CALLBACK)
        return
    if callback_data.target_id <= 0:
        await query.answer()
        return
    moved = await CategoryService(CategoryRepository(session)).merge(
        user.id, current_track, callback_data.category_id, callback_data.target_id
    )
    await query.answer(CATEGORY_MERGED.format(count=moved))
    await _show_overview(query, user, current_track, session)
