from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import SettingsCB
from app.bot.filters import InState
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.settings import (
    TZ_ZONES,
    goal_values_kb,
    new_pace_kb,
    pace_kb,
    push_settings_kb,
    level_screen_kb,
    push_window_kb,
    settings_kb,
    timezone_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    ERROR_GOAL_NOT_NUMBER,
    LEVEL_SCREEN,
    LEVEL_SCREEN_UNSET,
    ERROR_GOAL_TOO_BIG,
    ERROR_GOAL_TOO_SMALL,
    PACE_LABELS,
    PACE_TITLE,
    PLACEMENT_CARD,
    PLACEMENT_UNAVAILABLE,
    PUSH_PACE_SET,
    PUSH_PACE_TITLE,
    PUSH_TITLE,
    PUSH_WINDOW_TITLE,
    PUSH_WINDOW_TOO_SHORT,
    SETTINGS_GOAL_PROMPT,
    SETTINGS_GOAL_UPDATED,
    SETTINGS_TITLE,
    TZ_TITLE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, TRACK_LABELS
from app.domain.pacing import PACE_VALUES, label_for, pace_of
from app.domain.push import window_hours
from app.domain.models import User, UserTrack
from app.bot.keyboards.onboarding import placement_card_kb
from app.services.interaction_state_service import InteractionStateService
from app.services.placement_service import ORIGIN_SETTINGS, PlacementService
from app.services.user_service import UserService
from app.services.user_track_service import UserTrackService

router = Router(name="settings")


def _settings_text(user_track: UserTrack, current_track: LearningTrack) -> str:
    return SETTINGS_TITLE.format(
        track=TRACK_LABELS[current_track],
        goal=user_track.daily_goal_words,
        pace=PACE_LABELS.get(user_track.learning_pace, user_track.learning_pace),
    )


@router.callback_query(SettingsCB.filter(F.action == "open"))
async def on_open(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            _settings_text(user_track, current_track),
            reply_markup=settings_kb(),
            parse_mode="HTML",
        )
    await query.answer()


SETTINGS_GOAL_KIND = "set_goal"
SETTINGS_PACE_KIND = "set_pace"


@router.callback_query(SettingsCB.filter(F.action == "goal"))
async def on_goal(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    await state_service.clear(user.id)
    version = await screen_service.bump(user.id, SETTINGS_GOAL_KIND)
    if query.message:
        await query.message.edit_text(
            "Выбери дневную цель:", reply_markup=goal_values_kb(version=version)
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "goal_value"))
async def on_goal_value(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, SETTINGS_GOAL_KIND, callback_data.v):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return
    if callback_data.value == "custom":
        await state_service.set(user.id, InteractionState.SETTINGS_GOAL_INPUT)
        if query.message:
            await query.message.edit_text(SETTINGS_GOAL_PROMPT, reply_markup=cancel_only_kb())
        await query.answer()
        return

    try:
        value = int(callback_data.value)
    except ValueError:
        await query.answer()
        return

    if not UserService.is_valid_goal(value):
        await query.answer(ERROR_GOAL_TOO_BIG, show_alert=True)
        return

    await user_track_service.set_daily_goal(user.id, current_track, value)
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            SETTINGS_GOAL_UPDATED.format(goal=value), reply_markup=settings_kb()
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "pace"))
async def on_pace(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    await state_service.clear(user.id)
    version = await screen_service.bump(user.id, SETTINGS_PACE_KIND)
    if query.message:
        await query.message.edit_text(
            PACE_TITLE,
            reply_markup=pace_kb(user_track.learning_pace, version=version),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "pace_value"))
async def on_pace_value(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
    screen_service,
) -> None:
    if not await screen_service.check(user.id, SETTINGS_PACE_KIND, callback_data.v):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return
    try:
        pace = LearningPace(callback_data.value)
    except ValueError:
        await query.answer()
        return
    updated = await user_track_service.set_pace(user.id, current_track, pace)
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            _settings_text(updated, current_track), reply_markup=settings_kb(), parse_mode="HTML"
        )
    await query.answer()


@router.message(InState(InteractionState.SETTINGS_GOAL_INPUT), F.text)
async def on_settings_goal_text(
    message: Message,
    user: User,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
    state_service: InteractionStateService,
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

    await user_track_service.set_daily_goal(user.id, current_track, value)
    await state_service.clear(user.id)
    await message.answer(
        SETTINGS_GOAL_UPDATED.format(goal=value), reply_markup=settings_kb()
    )


# --------------------------------------------------------------------------- #
# Push-learning settings
# --------------------------------------------------------------------------- #


def _window(user_track: UserTrack) -> tuple[int, int]:
    cfg = get_settings()
    s = user_track.settings or {}
    return (
        int(s.get("push_ws", cfg.push_default_window_start)),
        int(s.get("push_we", cfg.push_default_window_end)),
    )


@router.callback_query(SettingsCB.filter(F.action == "push_open"))
async def on_push_open(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    ws, we = _window(user_track)
    if query.message:
        await query.message.edit_text(
            PUSH_TITLE,
            reply_markup=push_settings_kb(ws, we, pace_of(user_track.settings)),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "newpace"))
async def on_newpace_open(query: CallbackQuery, user_track: UserTrack) -> None:
    pace = pace_of(user_track.settings)
    if query.message:
        await query.message.edit_text(
            PUSH_PACE_TITLE.format(current=label_for(pace)),
            reply_markup=new_pace_kb(pace),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "newpace_set"))
async def on_newpace_set(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    current_track: LearningTrack,
    user_track: UserTrack,
    user_track_service: UserTrackService,
) -> None:
    try:
        value = int(callback_data.value or "")
    except ValueError:
        await query.answer()
        return
    if value not in PACE_VALUES:
        await query.answer()
        return
    await user_track_service.update_settings(user.id, current_track, {"new_pace": value})
    user_track.settings = {**(user_track.settings or {}), "new_pace": value}
    if query.message:
        await query.message.edit_reply_markup(reply_markup=new_pace_kb(value))
    await query.answer(PUSH_PACE_SET.format(label=label_for(value)))


@router.callback_query(SettingsCB.filter(F.action == "push_win"))
async def on_push_win(query: CallbackQuery, user_track: UserTrack) -> None:
    ws, we = _window(user_track)
    mh = get_settings().push_min_window_hours
    if query.message:
        await query.message.edit_text(PUSH_WINDOW_TITLE, reply_markup=push_window_kb(ws, we, mh), parse_mode="HTML")
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "push_win_set"))
async def on_push_win_set(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    current_track: LearningTrack,
    user_track: UserTrack,
    user_track_service: UserTrackService,
) -> None:
    mh = get_settings().push_min_window_hours
    # value = "<op>_<ws>_<we>" — the pending pair rides in the callback so the
    # grid can be navigated without persisting an intermediate (maybe <min) window.
    # op "w" = a cell was tapped (re-render pending), "sv" = save.
    parts = (callback_data.value or "").split("_")
    try:
        op, ws, we = parts[0], int(parts[1]), int(parts[2])
    except (IndexError, ValueError):
        await query.answer()
        return

    async def _rerender() -> None:
        # Re-tapping the already-selected hour yields an identical keyboard →
        # Telegram raises "message is not modified". That's benign for a picker.
        if query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=push_window_kb(ws, we, mh))
            except TelegramBadRequest:
                pass

    if op == "sv":
        if not (mh <= window_hours(ws, we) < 24):
            await query.answer(PUSH_WINDOW_TOO_SHORT, show_alert=True)
            return
        await user_track_service.update_settings(user.id, current_track, {"push_ws": ws, "push_we": we})
        # Saved → return to the push-settings screen (shows the new window).
        if query.message:
            try:
                await query.message.edit_text(
                    PUSH_TITLE,
                    reply_markup=push_settings_kb(ws, we, pace_of(user_track.settings)),
                    parse_mode="HTML",
                )
            except TelegramBadRequest:
                pass
        await query.answer(f"✅ {ws:02d}:00–{we:02d}:00")
        return

    # A cell tap: re-render with the new pending pair (not yet saved).
    await _rerender()
    await query.answer()


# --------------------------------------------------------------------------- #
# Timezone
# --------------------------------------------------------------------------- #

_VALID_TZ = {zone for zone, _ in TZ_ZONES}


@router.callback_query(SettingsCB.filter(F.action == "tz_open"))
async def on_tz_open(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    if query.message:
        await query.message.edit_text(
            TZ_TITLE.format(tz=user.timezone),
            reply_markup=timezone_kb(user.timezone),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "tz_set"))
async def on_tz_set(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    session: AsyncSession,
) -> None:
    zone = callback_data.value or ""
    if zone in _VALID_TZ and zone != user.timezone:
        user.timezone = zone
        await session.flush()
    if query.message:
        await query.message.edit_text(
            TZ_TITLE.format(tz=user.timezone),
            reply_markup=timezone_kb(user.timezone),
            parse_mode="HTML",
        )
    await query.answer(f"🕐 {user.timezone}")



@router.callback_query(SettingsCB.filter(F.action == "level"))
async def on_level_open(
    query: CallbackQuery,
    user: User,
    state_service: InteractionStateService,
) -> None:
    await state_service.clear(user.id)
    text = LEVEL_SCREEN.format(level=user.level) if user.level else LEVEL_SCREEN_UNSET
    if query.message:
        await query.message.edit_text(text, reply_markup=level_screen_kb(), parse_mode="HTML")
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "level_test"))
async def on_level_test(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    placement: PlacementService,
) -> None:
    """Retake the placement test from settings. The test itself is the same as
    in onboarding — only the ending differs, which the stored origin decides."""
    card = await placement.start(user.id, current_track, origin=ORIGIN_SETTINGS)
    if card is None:
        await query.answer(PLACEMENT_UNAVAILABLE, show_alert=True)
        return
    if query.message:
        await query.message.edit_text(
            PLACEMENT_CARD.format(
                writing=html.escape(card.writing), position=card.position, total=card.total
            ),
            reply_markup=placement_card_kb(card.options),
            parse_mode="HTML",
        )
    await query.answer()
