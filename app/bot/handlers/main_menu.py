from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import NavCB
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.keyboards.my_words import categories_overview_kb
from app.bot.keyboards.settings import settings_kb
from app.bot.keyboards.study import study_menu_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    ADD_WORDS_PROMPT,
    BTN_ADD,
    BTN_IMPORT,
    BTN_MY_WORDS,
    BTN_PACKS,
    BTN_PROGRESS,
    BTN_SETTINGS,
    BTN_STUDY,
    MAIN_MENU,
    MY_WORDS_EMPTY,
    PACE_LABELS,
    PROGRESS_TITLE,
    SETTINGS_TITLE,
    TXT_PROMPT,
)
from app.domain.enums import LearningTrack, TRACK_LABELS
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.categories import CategoryRepository
from app.services.category_service import CategoryService
from app.services.interaction_state_service import InteractionStateService
from app.services.progress_service import ProgressService
from app.services.user_track_service import UserTrackService

router = Router(name="main_menu")


async def send_main_menu(message: Message, text: str = MAIN_MENU) -> None:
    """Show (or refresh) the bottom menu."""
    await message.answer(text, reply_markup=main_menu_reply_kb())


# --------------------------------------------------------------------------- #
# Bottom reply-menu buttons. These arrive as plain text messages and are
# allowed in any state by InteractionGuard, so each one resets state first.
# --------------------------------------------------------------------------- #


@router.message(F.text == BTN_MY_WORDS)
async def msg_my_words(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    service = CategoryService(CategoryRepository(session))
    categories = await service.list_user_categories(user.id, current_track)
    counts = await service.counts(user.id, current_track)
    if sum(counts.values()) == 0 and not categories:
        await message.answer(MY_WORDS_EMPTY)
        return
    await message.answer(
        "📚 Мои слова",
        reply_markup=categories_overview_kb(categories, counts, flow="mw"),
    )


@router.message(F.text == BTN_STUDY)
async def msg_study(
    message: Message,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    await message.answer("🔥 Учить", reply_markup=study_menu_kb())


@router.message(F.text == BTN_ADD)
async def msg_add(
    message: Message,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_MANUAL_WORDS)
    await message.answer(ADD_WORDS_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML")


@router.message(F.text == BTN_IMPORT)
async def msg_import(
    message: Message,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.set(user.id, InteractionState.WAITING_TXT_FILE)
    await message.answer(TXT_PROMPT, reply_markup=cancel_only_kb(), parse_mode="HTML")


@router.message(F.text == BTN_PACKS)
async def msg_packs(
    message: Message,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    from app.bot.handlers.packs import open_packs

    await open_packs(message, user, current_track, session, state_service)


@router.message(F.text == BTN_PROGRESS)
async def msg_progress(
    message: Message,
    user: User,
    session: AsyncSession,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    progress = ProgressService(session)
    active = await user_track_service.list_active(user.id)
    lines = []
    for ut in active:
        track = LearningTrack(ut.track)
        view = await progress.track_view(
            user.id, track, ut.daily_goal_words, tz_name=user.timezone
        )
        lines.append(
            f"{TRACK_LABELS[track]}: <b>{view.studied_today}</b> / {view.daily_goal} | "
            f"📚 {view.total_words} • ✅ {view.mastered_words} • 🔥 {view.weak_words}"
        )
    text = PROGRESS_TITLE.format(streak=user.streak_days, per_track="\n".join(lines) or "—")
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == BTN_SETTINGS)
async def msg_settings(
    message: Message,
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
    await message.answer(text, reply_markup=settings_kb(), parse_mode="HTML")


# --------------------------------------------------------------------------- #
# In-flow inline navigation (Назад / Отмена / В меню). These end the current
# inline scenario; the persistent bottom menu stays available underneath.
# --------------------------------------------------------------------------- #


@router.callback_query(NavCB.filter(F.action.in_({"home", "cancel", "back"})))
async def on_nav(
    query: CallbackQuery,
    callback_data: NavCB,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    if query.message:
        try:
            await query.message.edit_text(MAIN_MENU)
        except Exception:  # noqa: BLE001 — message may be too old to edit
            pass
    await query.answer("Отменено." if callback_data.action == "cancel" else None)
