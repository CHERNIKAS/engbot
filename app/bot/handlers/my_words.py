from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import DeleteCB, MyWordsCB
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.my_words import (
    categories_overview_kb,
    category_words_kb,
    delete_confirm_kb,
    word_detail_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    DELETED,
    DELETE_CONFIRM,
    MY_WORDS_EMPTY,
    MY_WORDS_TITLE,
    STUDY_CARD_NO_TRANSLATION,
    STUDY_EXAMPLE_MISSING,
    WORD_DETAIL,
)
from app.domain.enums import LearningTrack, StudyMode, StudyScope
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.user_track_service import UserTrackService

router = Router(name="my_words")

PAGE_SIZE = 10


def _category_filter(category_id: int) -> tuple[str, int | None]:
    if category_id == 0:
        return "any", None
    if category_id == -1:
        return "uncategorized", None
    return "specific", category_id


async def _render_category(
    query: CallbackQuery,
    user: User,
    track: LearningTrack,
    session: AsyncSession,
    category_id: int,
    page: int,
) -> None:
    filt, cid = _category_filter(category_id)
    repo = UserWordRepository(session)
    rows, total = await repo.list_for_user(
        user_id=user.id,
        track=track,
        category_id=cid,
        category_filter=filt,
        limit=PAGE_SIZE,
        offset=page * PAGE_SIZE,
    )
    cat_name = "Все слова" if category_id == 0 else "Без категории"
    if category_id > 0:
        cat = await CategoryRepository(session).get(category_id)
        if cat is not None:
            cat_name = cat.name
    text = MY_WORDS_TITLE.format(category=cat_name, count=total)
    items = [(uw.id, w.writing) for uw, w in rows]
    has_next = (page + 1) * PAGE_SIZE < total
    if query.message:
        await query.message.edit_text(
            text,
            reply_markup=category_words_kb(category_id, items, page, has_next),
        )


@router.callback_query(MyWordsCB.filter(F.action == "open"))
async def on_open_category(
    query: CallbackQuery,
    callback_data: MyWordsCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
) -> None:
    await _render_category(query, user, current_track, session, callback_data.category_id, callback_data.page)
    await query.answer()


@router.callback_query(MyWordsCB.filter(F.action == "word"))
async def on_word_detail(
    query: CallbackQuery,
    callback_data: MyWordsCB,
    user: User,
    session: AsyncSession,
) -> None:
    pair = await UserWordRepository(session).get_with_word(callback_data.user_word_id)
    if pair is None:
        await query.answer("Не найдено.")
        return
    uw, word = pair
    translation = uw.custom_translation or word.translation or STUDY_CARD_NO_TRANSLATION
    example = word.example_sentence or STUDY_EXAMPLE_MISSING
    text = WORD_DETAIL.format(
        writing=html.escape(word.writing),
        translation=html.escape(translation),
        example=html.escape(example),
    )
    if query.message:
        await query.message.edit_text(
            text,
            reply_markup=word_detail_kb(uw.id, callback_data.category_id, callback_data.page),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(MyWordsCB.filter(F.action == "study_cat"))
async def on_study_category(
    query: CallbackQuery,
    callback_data: MyWordsCB,
    user: User,
    current_track,
    user_track,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session,
    screen_service,
    analytics,
) -> None:
    from app.bot.handlers.study import start_session

    await start_session(
        query=query,
        user=user,
        user_track=user_track,
        current_track=current_track,
        session=session,
        state_service=state_service,
        study_session=study_session,
        screen_service=screen_service,
        analytics=analytics,
        scope=StudyScope.CATEGORY,
        scope_ref_id=callback_data.category_id,
    )


DELETE_SCREEN_KIND = "del_confirm"


@router.callback_query(DeleteCB.filter(F.action == "ask"))
async def on_delete_ask(
    query: CallbackQuery,
    callback_data: DeleteCB,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    repo = UserWordRepository(session)
    pair = await repo.get_with_word(callback_data.user_word_id)
    if pair is None:
        await query.answer("Не найдено.")
        return
    _uw, word = pair
    version = await screen_service.bump(user.id, DELETE_SCREEN_KIND)
    await state_service.set(
        user.id,
        InteractionState.WAITING_DELETE_CONFIRMATION,
        {"user_word_id": callback_data.user_word_id, "flow": callback_data.flow},
    )
    if query.message:
        await query.message.edit_text(
            DELETE_CONFIRM.format(word=word.writing),
            reply_markup=delete_confirm_kb(
                callback_data.user_word_id, callback_data.flow, version=version
            ),
        )
    await query.answer()


@router.callback_query(DeleteCB.filter(F.action == "confirm"))
async def on_delete_confirm(
    query: CallbackQuery,
    callback_data: DeleteCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
    study_session,
    screen_service,
    user_track: UserTrack | None = None,
) -> None:
    if not await screen_service.check(user.id, DELETE_SCREEN_KIND, callback_data.v):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return
    if callback_data.flow == "st":
        from app.bot.handlers.study import handle_in_study_delete
        await handle_in_study_delete(
            query=query,
            user=user,
            user_track=user_track,
            session=session,
            state_service=state_service,
            study_session=study_session,
            screen_service=screen_service,
        )
        return

    repo = UserWordRepository(session)
    await repo.delete(callback_data.user_word_id)
    await state_service.clear(user.id)
    await query.answer(DELETED)
    cat_service = CategoryService(CategoryRepository(session))
    categories = await cat_service.list_user_categories(user.id, current_track)
    counts = await cat_service.counts(user.id, current_track)
    if sum(counts.values()) == 0 and not categories:
        if query.message:
            await query.message.edit_text(MY_WORDS_EMPTY, reply_markup=None)
        return
    if query.message:
        await query.message.edit_text(
            "📚 Мои слова",
            reply_markup=categories_overview_kb(categories, counts, flow="mw"),
        )


@router.callback_query(DeleteCB.filter(F.action == "cancel"))
async def on_delete_cancel(
    query: CallbackQuery,
    callback_data: DeleteCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
    study_session,
    screen_service,
) -> None:
    if callback_data.flow == "st":
        await state_service.set(user.id, InteractionState.STUDY_ACTIVE)
        from app.bot.handlers.study import render_current_card
        await render_current_card(query, user, session, state_service, study_session, screen_service)
        await query.answer()
        return
    await state_service.clear(user.id)
    # Back to the word list rather than a "Главное меню" stub.
    cat_service = CategoryService(CategoryRepository(session))
    categories = await cat_service.list_user_categories(user.id, current_track)
    counts = await cat_service.counts(user.id, current_track)
    if query.message:
        if sum(counts.values()) == 0 and not categories:
            await query.message.edit_text(MY_WORDS_EMPTY, reply_markup=None)
        else:
            await query.message.edit_text(
                "📚 Мои слова",
                reply_markup=categories_overview_kb(categories, counts, flow="mw"),
            )
    await query.answer()
