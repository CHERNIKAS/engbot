from __future__ import annotations


from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks.schema import OnboardingCB
from app.bot.filters import InState
from app.config import get_settings
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.keyboards.onboarding import (
    onboarding_intro_kb,
    tracks_picker_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    ASK_TRACKS,
    INTRO,
    MAIN_MENU,
    ONBOARDING_DONE,
    ONBOARDING_EXPIRED,
    PASSWORD_OK,
    PASSWORD_PROMPT,
    PASSWORD_WRONG,
)
from app.domain.enums import LearningTrack, enabled_tracks
from app.domain.models import User
from app.services.analytics import (
    EVENT_ONBOARDING_COMPLETED,
    Analytics,
)
from app.services.interaction_state_service import InteractionStateService
from app.services.track_context_service import TrackContextService
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
    # They're back — if push was auto-disabled (they'd blocked the bot), re-enable.
    await user_track_service.update_settings(user.id, current_track, {"push_blocked": False})

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



async def _finish_setup(
    query: CallbackQuery,
    *,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
    tracks: set[LearningTrack],
) -> None:
    """Close out setup. Nothing else is asked.

    This used to hand straight to the placement test — twelve questions whose
    answer the first plan overwrites anyway, since the level is derived from
    mastered words now. Asking them would spend a new learner's first minute on
    a number we throw away, and it would be the first thing they see of the bot.

    A beginner starts at A1 by simple arithmetic: nothing mastered, nothing in
    either frequency band. The daily-goal question went the same way earlier,
    for the same reason — friction that shaped nothing.
    """
    await _finalize_onboarding(
        user=user,
        state_service=state_service,
        user_track_service=user_track_service,
        track_context=track_context,
        analytics=analytics,
        tracks=tracks,
        daily_goal=get_settings().default_daily_goal,
    )
    if query.message:
        await query.message.edit_text(ONBOARDING_DONE, parse_mode="HTML")
        await query.message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "start"))
async def on_start_clicked(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
) -> None:
    allowed = enabled_tracks(get_settings().enable_japanese)
    selected = {LearningTrack.ENGLISH}
    if len(allowed) == 1:
        # Only English available — skip the picker entirely.
        await _finish_setup(
            query,
            user=user,
            state_service=state_service,
            user_track_service=user_track_service,
            track_context=track_context,
            analytics=analytics,
            tracks=selected,
        )
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
        await query.answer(ONBOARDING_EXPIRED, show_alert=False)
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
    user_track_service: UserTrackService,
    track_context: TrackContextService,
    analytics: Analytics,
) -> None:
    payload = await state_service.get(user.id)
    if payload.state != InteractionState.ONBOARDING_TRACKS:
        await query.answer(ONBOARDING_EXPIRED, show_alert=False)
        return
    await _finish_setup(
        query,
        user=user,
        state_service=state_service,
        user_track_service=user_track_service,
        track_context=track_context,
        analytics=analytics,
        tracks=_selected_tracks(payload.data) or {LearningTrack.ENGLISH},
    )


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


