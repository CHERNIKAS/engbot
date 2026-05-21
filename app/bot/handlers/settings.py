from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import SettingsCB
from app.bot.filters import InState
from app.bot.keyboards.common import cancel_only_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.settings import (
    goal_values_kb,
    pace_kb,
    push_settings_kb,
    push_window_kb,
    settings_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    ERROR_GOAL_NOT_NUMBER,
    ERROR_GOAL_TOO_BIG,
    ERROR_GOAL_TOO_SMALL,
    PACE_LABELS,
    PUSH_TITLE,
    PUSH_WINDOW_TITLE,
    PUSH_WINDOW_TOO_SHORT,
    SETTINGS_GOAL_PROMPT,
    SETTINGS_GOAL_UPDATED,
    SETTINGS_TITLE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, TRACK_LABELS
from app.domain.models import User, UserTrack
from app.services.interaction_state_service import InteractionStateService
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
            "Выбери темп обучения:",
            reply_markup=pace_kb(user_track.learning_pace, version=version),
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
            PUSH_TITLE, reply_markup=push_settings_kb(ws, we), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "push_win"))
async def on_push_win(query: CallbackQuery, user_track: UserTrack) -> None:
    ws, we = _window(user_track)
    if query.message:
        await query.message.edit_text(PUSH_WINDOW_TITLE, reply_markup=push_window_kb(ws, we))
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
    cfg = get_settings()
    ws, we = _window(user_track)
    val = callback_data.value or ""
    try:
        kind, hour = val[0], int(val[1:])
    except (IndexError, ValueError):
        await query.answer()
        return
    new_ws, new_we = (hour, we) if kind == "s" else (ws, hour)
    if new_we - new_ws < cfg.push_min_window_hours:
        await query.answer(PUSH_WINDOW_TOO_SHORT, show_alert=True)
        return
    await user_track_service.update_settings(
        user.id, current_track, {"push_ws": new_ws, "push_we": new_we}
    )
    if query.message:
        await query.message.edit_reply_markup(reply_markup=push_window_kb(new_ws, new_we))
    await query.answer(f"{new_ws:02d}:00–{new_we:02d}:00")
