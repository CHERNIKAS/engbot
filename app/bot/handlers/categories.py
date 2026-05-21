from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import CategoryCB
from app.bot.filters import InState
from app.bot.keyboards.add_words import add_choose_category_kb
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_CHOOSE_CATEGORY,
    CATEGORY_CREATED,
    CATEGORY_NEW_EMPTY,
    CATEGORY_NEW_EXISTS,
    CATEGORY_NEW_PROMPT,
    CATEGORY_NEW_TOO_LONG,
    MAIN_MENU,
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
