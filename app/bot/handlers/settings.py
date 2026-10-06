from __future__ import annotations


from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import SettingsCB
from app.bot.keyboards.settings import (
    TZ_ZONES,
    pace_kb,
    push_settings_kb,
    level_screen_kb,
    push_window_kb,
    settings_kb,
    timezone_kb,
)
from app.bot.texts import (
    LEVEL_SCREEN,
    PACE_LABELS,
    PACE_TITLE,
    PUSH_TITLE,
    PUSH_WINDOW_TITLE,
    PUSH_WINDOW_PENDING,
    PUSH_WINDOW_TOO_SHORT,
    SETTINGS_TITLE,
    TZ_TITLE,
)
from app.config import get_settings
from app.logging_setup import get_logger
from app.domain.enums import LearningPace, LearningTrack, TRACK_LABELS
from app.domain.pacing import pace_of
from app.domain.push import window_hours
from app.domain.levels import level_from_coverage
from app.domain.models import User, UserTrack
from app.infrastructure.repositories.user_words import UserWordRepository
from app.services.interaction_state_service import InteractionStateService
from app.services.user_track_service import UserTrackService

log = get_logger("settings")

router = Router(name="settings")


def _settings_text(user_track: UserTrack, current_track: LearningTrack) -> str:
    return SETTINGS_TITLE.format(
        track=TRACK_LABELS[current_track],
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


SETTINGS_PACE_KIND = "set_pace"


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


@router.callback_query(SettingsCB.filter(F.action == "push_win"))
async def on_push_win(query: CallbackQuery, user_track: UserTrack) -> None:
    ws, we = _window(user_track)
    mh = get_settings().push_min_window_hours
    if query.message:
        await query.message.edit_text(
            PUSH_WINDOW_TITLE.format(min_hours=mh),
            reply_markup=push_window_kb(ws, we, mh, step="ws"),
            parse_mode="HTML",
        )
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
    # grid can be navigated without persisting an intermediate (maybe <min)
    # window. The op says which grid to show next:
    #   "w"  a start hour was picked        → show the end grid
    #   "e"  an end hour was picked         → stay on the end grid
    #   "b"  «change the start» was tapped  → back to the start grid
    #   "sv" save
    parts = (callback_data.value or "").split("_")
    try:
        op, ws, we = parts[0], int(parts[1]), int(parts[2])
    except (IndexError, ValueError):
        await query.answer()
        return

    step = "ws" if op == "b" else "we"

    async def _rerender() -> None:
        # Re-tapping the already-selected hour yields an identical keyboard →
        # Telegram raises "message is not modified". That's benign for a picker.
        # Anything else is not: a swallowed failure here leaves the OLD grid on
        # screen, so the next tap sends the OLD pending pair and the user's
        # first choice is silently lost. Log it rather than lose it.
        if query.message:
            try:
                await query.message.edit_reply_markup(
                    reply_markup=push_window_kb(ws, we, mh, step=step)
                )
            except TelegramBadRequest as exc:
                if "not modified" not in str(exc).lower():
                    log.warning("push_window_rerender_failed", error=str(exc), ws=ws, we=we)

    if op == "sv":
        if not (mh <= window_hours(ws, we) < 24):
            await query.answer(PUSH_WINDOW_TOO_SHORT.format(min_hours=mh), show_alert=True)
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

    if op not in ("w", "e", "b"):
        await query.answer()
        return

    # A cell tap: re-render with the new pending pair (not yet saved). The toast
    # repeats the pending window, so the user can see their tap landed even if
    # the grid itself fails to redraw — and can tell us what it said.
    await _rerender()
    await query.answer(PUSH_WINDOW_PENDING.format(ws=ws, we=we, hours=window_hours(ws, we)))


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
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
) -> None:
    """The level shown next to the numbers it comes from.

    A bare «A1» reads as a verdict; «первая тысяча: 340 из 1044» reads as a
    measurement, and makes it obvious what moves it.
    """
    await state_service.clear(user.id)
    band1, band2, total1, total2 = await UserWordRepository(session).band_coverage(
        user.id, current_track
    )
    text = LEVEL_SCREEN.format(
        level=user.level or level_from_coverage(band1, band2),
        band1=band1,
        band1_total=total1,
        band2=band2,
        band2_total=total2,
    )
    if query.message:
        await query.message.edit_text(
            text, reply_markup=level_screen_kb(user.level), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "style_open"))
async def on_phrase_style_open(query: CallbackQuery, user_track: UserTrack) -> None:
    from app.bot.keyboards.settings import phrase_style_settings_kb
    from app.bot.texts import PHRASE_STYLE_SETTINGS

    current = (user_track.settings or {}).get("phrase_style", "ask")
    if query.message:
        await query.message.edit_text(
            PHRASE_STYLE_SETTINGS, reply_markup=phrase_style_settings_kb(current), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(SettingsCB.filter(F.action == "style_set"))
async def on_phrase_style_set(
    query: CallbackQuery,
    callback_data: SettingsCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    user_track_service: UserTrackService,
) -> None:
    from app.bot.keyboards.settings import phrase_style_settings_kb
    from app.bot.texts import PHRASE_STYLE_DEFAULTS, PHRASE_STYLE_SETTINGS

    value = callback_data.value if callback_data.value in PHRASE_STYLE_DEFAULTS else "ask"
    await user_track_service.update_settings(user.id, current_track, {"phrase_style": value})
    if query.message:
        try:
            await query.message.edit_text(
                PHRASE_STYLE_SETTINGS, reply_markup=phrase_style_settings_kb(value), parse_mode="HTML"
            )
        except Exception:  # noqa: BLE001 — unchanged when the same option is tapped
            pass
    await query.answer(f"🗣 {PHRASE_STYLE_DEFAULTS[value]}")
