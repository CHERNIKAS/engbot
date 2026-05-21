from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import MainMenuCB, NavCB
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.my_words import categories_overview_kb
from app.bot.keyboards.packs import pack_categories_kb
from app.bot.keyboards.settings import settings_kb
from app.bot.keyboards.study import study_menu_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_WORDS_PROMPT,
    MAIN_MENU,
    MY_WORDS_EMPTY,
    PACE_LABELS,
    PACKS_PICK_CATEGORIES,
    PROGRESS_TITLE,
    SETTINGS_TITLE,
    TXT_PROMPT,
)
from app.domain.enums import LearningTrack, TRACK_LABELS
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.categories import CategoryRepository
from app.infrastructure.repositories.packs import PackRepository
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.progress_service import ProgressService
from app.services.track_context_service import TrackContextService
from app.services.user_track_service import UserTrackService

router = Router(name="main_menu")


def _menu_text(active_tracks: list[UserTrack], current_track: LearningTrack) -> str:
    if len(active_tracks) <= 1:
        return MAIN_MENU
    return f"{MAIN_MENU}\nТекущий трек: <b>{TRACK_LABELS[current_track]}</b>"


@router.callback_query(NavCB.filter(F.action == "home"))
async def on_home(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    active = await user_track_service.list_active(user.id)
    if query.message:
        await query.message.edit_text(
            _menu_text(active, current_track),
            reply_markup=main_menu_kb(active, current_track),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(NavCB.filter(F.action == "cancel"))
async def on_cancel(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    active = await user_track_service.list_active(user.id)
    if query.message:
        await query.message.edit_text(
            _menu_text(active, current_track),
            reply_markup=main_menu_kb(active, current_track),
            parse_mode="HTML",
        )
    await query.answer("Отменено.")


@router.callback_query(NavCB.filter(F.action == "back"))
async def on_back(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    active = await user_track_service.list_active(user.id)
    if query.message:
        await query.message.edit_text(
            _menu_text(active, current_track),
            reply_markup=main_menu_kb(active, current_track),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "track"))
async def on_track_switch(
    query: CallbackQuery,
    callback_data: MainMenuCB,
    user: User,
    track_context: TrackContextService,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    try:
        new_track = LearningTrack(callback_data.value)
    except ValueError:
        await query.answer()
        return
    from app.config import get_settings as _gs
    from app.domain.enums import enabled_tracks as _enabled
    if new_track not in _enabled(_gs().enable_japanese):
        await query.answer("Этот трек пока недоступен.", show_alert=False)
        return
    ut = await user_track_service.get(user.id, new_track)
    if ut is None or not ut.is_active:
        await query.answer("Этот трек не активен.", show_alert=True)
        return
    await track_context.set(user.id, new_track)
    await state_service.clear(user.id)
    active = await user_track_service.list_active(user.id)
    if query.message:
        await query.message.edit_text(
            _menu_text(active, new_track),
            reply_markup=main_menu_kb(active, new_track),
            parse_mode="HTML",
        )
    await query.answer(f"{TRACK_LABELS[new_track]}")


@router.callback_query(MainMenuCB.filter(F.section == "words"))
async def on_my_words(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
) -> None:
    await state_service.clear(user.id)
    service = CategoryService(CategoryRepository(session))
    categories = await service.list_user_categories(user.id, current_track)
    counts = await service.counts(user.id, current_track)
    if sum(counts.values()) == 0 and not categories:
        active = await user_track_service.list_active(user.id)
        if query.message:
            await query.message.edit_text(
                MY_WORDS_EMPTY,
                reply_markup=main_menu_kb(active, current_track),
            )
        await query.answer()
        return
    if query.message:
        await query.message.edit_text(
            "📚 Мои слова",
            reply_markup=categories_overview_kb(categories, counts, flow="mw"),
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "study"))
async def on_study_menu(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text("🔥 Учить", reply_markup=study_menu_kb())
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "add"))
async def on_add_words(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_MANUAL_WORDS)
    if query.message:
        await query.message.edit_text(
            ADD_WORDS_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "import"))
async def on_import(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_TXT_FILE)
    if query.message:
        await query.message.edit_text(
            TXT_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "packs"))
async def on_packs(
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
            reply_markup=pack_categories_kb(categories, selected=set()),
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "progress"))
async def on_progress(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    progress = ProgressService(session)
    active = await user_track_service.list_active(user.id)
    track_lines = []
    for ut in active:
        track = LearningTrack(ut.track)
        view = await progress.track_view(
            user.id, track, ut.daily_goal_words, tz_name=user.timezone
        )
        track_lines.append(
            f"{TRACK_LABELS[track]}: <b>{view.studied_today}</b> / {view.daily_goal} | "
            f"📚 {view.total_words} • ✅ {view.mastered_words} • 🔥 {view.weak_words}"
        )
    text = PROGRESS_TITLE.format(
        streak=user.streak_days,
        per_track="\n".join(track_lines) if track_lines else "—",
    )
    if query.message:
        await query.message.edit_text(
            text, reply_markup=main_menu_kb(active, current_track), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(MainMenuCB.filter(F.section == "settings"))
async def on_settings(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    text = SETTINGS_TITLE.format(
        track=TRACK_LABELS[current_track],
        goal=user_track.daily_goal_words,
        pace=PACE_LABELS.get(user_track.learning_pace, user_track.learning_pace),
    )
    if query.message:
        await query.message.edit_text(text, reply_markup=settings_kb(), parse_mode="HTML")
    await query.answer()
