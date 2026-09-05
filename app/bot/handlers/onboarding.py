from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks.schema import OnboardingCB
from app.bot.filters import InState
from app.config import get_settings
from app.bot.keyboards.main_menu import main_menu_reply_kb
from app.bot.keyboards.course import course_onboarding_offer_kb
from app.bot.keyboards.onboarding import (
    onboarding_intro_kb,
    placement_card_kb,
    placement_intro_kb,
    tracks_picker_kb,
)
from app.bot.keyboards.settings import level_screen_kb
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
    PLACEMENT_CARD,
    PLACEMENT_INTRO,
    PLACEMENT_RESULT,
    PLACEMENT_UNAVAILABLE,
    PLACEMENT_GATE_DONE,
    LEVEL_UPDATED,
)
from app.domain.enums import LearningTrack, enabled_tracks
from app.domain.levels import DEFAULT_LEVEL
from app.domain.models import User
from app.services.placement_service import (
    ORIGIN_GATE,
    ORIGIN_SETTINGS,
    PlacementCard,
    PlacementService,
)
from app.services.analytics import (
    EVENT_ONBOARDING_COMPLETED,
    EVENT_PLACEMENT_COMPLETED,
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
    """Close out setup and hand straight to the placement test.

    The daily-goal question used to sit here. It set a number that now decides
    nothing — the active pool is sized from measured throughput and the progress
    bar compares each user against their own typical day — so asking for it was
    friction that shaped nothing.
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
        await query.message.edit_text(PLACEMENT_INTRO, reply_markup=placement_intro_kb())
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


async def _show_card(query: CallbackQuery, card: PlacementCard) -> None:
    """Render one placement question onto the live card.

    The three entry points into the test all draw the same card, and each used
    to do it by hand. One of them forgot `parse_mode`, so the word came out as
    a literal `<b>prove</b>` — a bug the user saw before any test did. Sending
    it from one place is what stops that recurring.
    """
    if query.message is None:
        return
    await query.message.edit_text(
        PLACEMENT_CARD.format(writing=html.escape(card.writing), position=card.position),
        reply_markup=placement_card_kb(card.options),
        parse_mode="HTML",
    )


async def _close_onboarding(query: CallbackQuery, text: str) -> None:
    """Last screen of onboarding — same ending for every placement outcome."""
    if query.message:
        await query.message.edit_text(
            f"{text}\n\n{ONBOARDING_DONE}",
            reply_markup=course_onboarding_offer_kb(),
            parse_mode="HTML",  # `text` carries the level in <b>…</b>
        )
        await query.message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())


@router.callback_query(OnboardingCB.filter(F.action == "lvl_start"))
async def on_placement_start(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    placement: PlacementService,
) -> None:
    card = await placement.start(user.id, current_track)
    if card is None:
        # Not enough catalogue at some level to ask a fair question. Placing the
        # user at the default beats blocking onboarding on a content gap.
        user.level = DEFAULT_LEVEL
        await _close_onboarding(query, PLACEMENT_UNAVAILABLE)
        await query.answer()
        return
    await _show_card(query, card)
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "lvl_gate"))
async def on_placement_gate_start(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    placement: PlacementService,
) -> None:
    """Entry point for a user held by the placement gate."""
    card = await placement.start(user.id, current_track, origin=ORIGIN_GATE)
    if card is None:
        # A content gap must never lock someone out of their own bot.
        user.level = DEFAULT_LEVEL
        if query.message:
            await query.message.edit_text(PLACEMENT_UNAVAILABLE)
        await query.answer()
        return
    await _show_card(query, card)
    await query.answer()


@router.callback_query(OnboardingCB.filter(F.action == "lvl"))
async def on_placement_answer(
    query: CallbackQuery,
    callback_data: OnboardingCB,
    user: User,
    state_service: InteractionStateService,
    placement: PlacementService,
    analytics: Analytics,
) -> None:
    card, verdict = await placement.answer(user.id, callback_data.value)
    if card is not None:
        await _show_card(query, card)
        await query.answer()
        return
    if verdict is None:
        # State expired mid-test (Redis TTL) — nothing to score, don't guess.
        await query.answer(ONBOARDING_EXPIRED, show_alert=True)
        return
    origin = await placement.origin_of(user.id)
    await analytics.emit(
        EVENT_PLACEMENT_COMPLETED,
        user_id=user.id,
        level=verdict,
        # Where they came from separates a first placement from a retake, and a
        # retake is the only signal that the first verdict felt wrong to them.
        origin=origin,
        previous=user.level,
    )
    user.level = verdict
    await state_service.clear(user.id)
    if origin == ORIGIN_GATE:
        # They were locked out; hand them the working bot, not a settings screen.
        if query.message:
            await query.message.edit_text(
                PLACEMENT_GATE_DONE.format(level=verdict), parse_mode="HTML"
            )
            await query.message.answer(MAIN_MENU, reply_markup=main_menu_reply_kb())
        await query.answer()
        return
    if origin == ORIGIN_SETTINGS:
        # Retaken from settings: the user is mid-session, so land them back on
        # the settings screen instead of replaying the end of onboarding.
        if query.message:
            await query.message.edit_text(
                LEVEL_UPDATED.format(level=verdict),
                reply_markup=level_screen_kb(),
                parse_mode="HTML",
            )
        await query.answer()
        return
    await _close_onboarding(query, PLACEMENT_RESULT.format(level=verdict))
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


