from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks.schema import OnboardingCB
from app.bot.filters import InState
from app.config import get_settings
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.keyboards.onboarding import (
    daily_goal_kb,
    onboarding_intro_kb,
    tracks_picker_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    ASK_CUSTOM_GOAL,
    ASK_DAILY_GOAL,
    ASK_TRACKS,
    ERROR_GOAL_NOT_NUMBER,
    ERROR_GOAL_TOO_BIG,
    ERROR_GOAL_TOO_SMALL,
    INTRO,
    MAIN_MENU,
    ONBOARDING_DONE,
    PASSWORD_OK,
    PASSWORD_PROMPT,
    PASSWORD_WRONG,
)
from app.domain.enums import LearningTrack, enabled_tracks
from app.domain.models import User
from app.services.analytics import EVENT_ONBOARDING_COMPLETED, Analytics
from app.services.interaction_state_service import InteractionStateService
from app.services.track_context_service import TrackContextService
from app.services.user_service import UserService
from app.services.user_track_service import UserTrackService

router = Router(name="onboarding")


def _selected_tracks(payload_data: dict) -> set[LearningTrack]:
    raw = (payload_data or {}).get("tracks") or []
    out: set[LearningTrack] = set()
    for v in raw:
        try:
            out.add(LearningTrack(v))
        except ValueError:
            continue
    return out


async def _finalize_onboarding(
    *,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
    tracks: set[LearningTrack],
    daily_goal: int,
) -> None:
    if not tracks:
        tracks = {LearningTrack.ENGLISH}
    await user_track_service.set_active_tracks(user.id, tracks)
    for t in tracks:
        await user_track_service.set_daily_goal(user.id, t, daily_goal)
        await user_track_service.complete_onboarding(user.id, t)
    await track_context.set(user.id, next(iter(sorted(tracks, key=lambda t: t.value))))
    user.onboarding_completed = True
    await analytics.emit(
        EVENT_ONBOARDING_COMPLETED,
        user_id=user.id,
        daily_goal=daily_goal,
        tracks=[t.value for t in tracks],
    )
    await state_service.clear(user.id)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    current_track: LearningTrack,
) -> None:
    # /start always resets state.
    await state_service.clear(user.id)

    if get_settings().access_password and not user.is_authorized:
        await state_service.set(user.id, InteractionState.WAITING_PASSWORD)
        await message.answer(PASSWORD_PROMPT)
        return

    if user.onboarding_completed:
        await message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
        return
    await state_service.set(
        user.id,
        InteractionState.ONBOARDING_TRACKS,
        {"tracks": [LearningTrack.ENGLISH.value]},
    )
    await message.answer(INTRO, reply_markup=onboarding_intro_kb(), parse_mode="HTML")


@router.message(InState(InteractionState.WAITING_PASSWORD), F.text)
async def on_password_text(
    message: Message,
    user: User,
    state_service: InteractionStateService,
) -> None:
    expected = get_settings().access_password
    received = (message.text or "").strip()
    if not expected or received != expected:
        await message.answer(PASSWORD_WRONG)
        return
    user.is_authorized = True
    await state_service.set(
        user.id,
        InteractionState.ONBOARDING_TRACKS,
        {"tracks": [LearningTrack.ENGLISH.value]},
    )
    await message.answer(PASSWORD_OK)
    await message.answer(INTRO, reply_markup=onboarding_intro_kb(), parse_mode="HTML")


@router.callback_query(OnboardingCB.filter(F.action == "start"))
async def on_start_clicked(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    allowed = enabled_tracks(get_settings().enable_japanese)
    selected = {LearningTrack.ENGLISH}
    if len(allowed) == 1:
        # Only English available — skip the picker entirely.
        await state_service.set(
            user.id,
            InteractionState.ONBOARDING_DAILY_GOAL,
            {"tracks": [t.value for t in selected]},
        )
        if query.message:
            await query.message.edit_text(ASK_DAILY_GOAL, reply_markup=daily_goal_kb())
        await query.answer()
        return

    await state_service.set(
        user.id,
        InteractionState.ONBOARDING_TRACKS,
        {"tracks": [t.value for t in selected]},
    )
    if query.message:
        await query.message.edit_text(
            ASK_TRACKS, reply_markup=tracks_picker_kb(selected, allowed=allowed)
        )
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "toggle_track"))
async def on_toggle_track(
    query: CallbackQuery,
    callback_data: OnboardingCB,
    user: User,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.ONBOARDING_TRACKS:
        await query.answer()
        return
    allowed = enabled_tracks(get_settings().enable_japanese)
    selected = _selected_tracks(payload.data)
    try:
        t = LearningTrack(callback_data.track)
    except ValueError:
        await query.answer()
        return
    if t not in allowed:
        await query.answer("Этот трек пока недоступен.", show_alert=False)
        return
    if t in selected:
        selected.discard(t)
    else:
        selected.add(t)
    if not selected:
        await query.answer("Нужен хотя бы один трек.", show_alert=False)
        return
    await state_service.update_data(user.id, tracks=[x.value for x in selected])
    if query.message:
        await query.message.edit_reply_markup(reply_markup=tracks_picker_kb(selected, allowed=allowed))
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "tracks_done"))
async def on_tracks_done(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.ONBOARDING_TRACKS:
        await query.answer()
        return
    selected = _selected_tracks(payload.data) or {LearningTrack.ENGLISH}
    await state_service.set(
        user.id,
        InteractionState.ONBOARDING_DAILY_GOAL,
        {"tracks": [t.value for t in selected]},
    )
    if query.message:
        await query.message.edit_text(ASK_DAILY_GOAL, reply_markup=daily_goal_kb())
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "goal"))
async def on_goal_picked(
    query: CallbackQuery,
    callback_data: OnboardingCB,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
) -> None:
    value = callback_data.value
    if not UserService.is_valid_goal(value):
        await query.answer(ERROR_GOAL_TOO_BIG, show_alert=True)
        return
    payload = await state_service.get(user.id)
    tracks = _selected_tracks(payload.data) or {LearningTrack.ENGLISH}
    await _finalize_onboarding(
        user=user,
        state_service=state_service,
        user_track_service=user_track_service,
        track_context=track_context,
        analytics=analytics,
        tracks=tracks,
        daily_goal=value,
    )
    if query.message:
        await query.message.edit_text(ONBOARDING_DONE)
        await query.message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "custom"))
async def on_custom_goal(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    payload = await state_service.get(user.id)
    tracks = list(_selected_tracks(payload.data) or {LearningTrack.ENGLISH})
    await state_service.set(
        user.id,
        InteractionState.ONBOARDING_CUSTOM_GOAL,
        {"tracks": [t.value for t in tracks]},
    )
    if query.message:
        await query.message.edit_text(ASK_CUSTOM_GOAL)
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "done"))
async def on_done(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    if query.message:
        await query.message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
    await query.answer()


@router.message(InState(InteractionState.ONBOARDING_CUSTOM_GOAL), F.text)
async def on_custom_goal_text(
    message: Message,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
    interaction_state,
) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(ERROR_GOAL_NOT_NUMBER)
        return
    value = int(text)
    if value < UserService.MIN_GOAL:
        await message.answer(ERROR_GOAL_TOO_SMALL)
        return
    if value > UserService.MAX_GOAL:
        await message.answer(ERROR_GOAL_TOO_BIG)
        return

    tracks = _selected_tracks(interaction_state.data) or {LearningTrack.ENGLISH}
    await _finalize_onboarding(
        user=user,
        state_service=state_service,
        user_track_service=user_track_service,
        track_context=track_context,
        analytics=analytics,
        tracks=tracks,
        daily_goal=value,
    )
    await message.answer(ONBOARDING_DONE)
    await message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
