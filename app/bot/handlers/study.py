from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import StudyCB
from app.bot.filters import InState
from app.bot.keyboards.study import finished_kb, quiz_card_kb, typing_card_kb
from app.bot.states import InteractionState
from app.bot.texts import (
    MAIN_MENU,
    STUDY_ANSWER_CORRECT,
    STUDY_ANSWER_WRONG,
    STUDY_FINISHED,
    STUDY_NO_WORDS,
    STUDY_QUIZ_PROMPT,
    STUDY_TYPE_PROMPT,
    STUDY_USE_BUTTONS,
)
from app.domain.enums import LearningTrack, StudyScope
from app.domain.models import User, UserTrack
from app.domain.study_drill import STAGE_QUIZ, is_typing_correct
from app.services.analytics import EVENT_STUDY_COMPLETED, EVENT_STUDY_STARTED, Analytics
from app.services.interaction_state_service import InteractionStateService
from app.services.progress_service import ProgressService
from app.services.screen_service import ScreenVersionService
from app.services.study_session_service import CardView, StudySessionService

router = Router(name="study")

SCREEN_KIND = "study_card"
_BAR_WIDTH = 10


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def _romaji_enabled(user_track: UserTrack | None) -> bool:
    if user_track is None:
        return True
    return bool((user_track.settings or {}).get("romaji_enabled", True))


def _progress_bar(learned: int, total: int) -> str:
    if total <= 0:
        return ""
    filled = max(0, min(_BAR_WIDTH, round(_BAR_WIDTH * learned / total)))
    return "▓" * filled + "░" * (_BAR_WIDTH - filled)


def _card_text(view: CardView, romaji_enabled: bool) -> str:
    bar = _progress_bar(view.learned, view.total)
    head = f"{bar} {view.learned}/{view.total} освоено · 🔁 {max(0, view.total - view.learned)}"
    is_ja = view.script_type is not None and view.script_type != "latin"
    if view.stage == STAGE_QUIZ:
        prompt = view.writing
        if is_ja and view.kana and view.kana != view.writing:
            prompt = f"{view.writing} ({view.kana})"
        body = f"{STUDY_QUIZ_PROMPT}\n\n<b>{prompt}</b>"
    else:
        body = f"{STUDY_TYPE_PROMPT}\n\n<b>{view.translation}</b>"
    return f"{head}\n\n{body}"


def _card_kb(view: CardView, version: str):
    if view.stage == STAGE_QUIZ:
        return quiz_card_kb(view.options, version, view.uw_id)
    return typing_card_kb(version, view.uw_id)


async def _check_screen(
    query: CallbackQuery, user_id: int, screen_service: ScreenVersionService, version: str
) -> bool:
    if not await screen_service.check(user_id, SCREEN_KIND, version):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return False
    return True


async def _render_edit(
    query: CallbackQuery,
    user: User,
    view: CardView,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None,
) -> None:
    version = await screen_service.bump(user.id, SCREEN_KIND)
    text = _card_text(view, _romaji_enabled(user_track))
    if query.message:
        await query.message.edit_text(text, reply_markup=_card_kb(view, version), parse_mode="HTML")


async def _render_send(
    message: Message,
    user: User,
    view: CardView,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None,
    prefix: str = "",
) -> None:
    version = await screen_service.bump(user.id, SCREEN_KIND)
    body = _card_text(view, _romaji_enabled(user_track))
    text = f"{prefix}\n\n{body}" if prefix else body
    await message.answer(text, reply_markup=_card_kb(view, version), parse_mode="HTML")


async def _finalize(
    user: User,
    user_track: UserTrack | None,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
) -> str:
    """Persist SR + streak; return the summary text (or MAIN_MENU)."""
    await state_service.clear(user.id)
    if user_track is None:
        await study_session.clear(user.id)
        return MAIN_MENU
    summary = await study_session.finish(user, user_track)
    await ProgressService(session).update_streak(user)
    if summary is None:
        return MAIN_MENU
    return STUDY_FINISHED.format(
        learned=summary.learned, total=summary.total, mistakes=summary.mistakes
    )


async def _finish_edit(
    query: CallbackQuery,
    user: User,
    user_track: UserTrack | None,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    analytics: Analytics | None = None,
) -> None:
    text = await _finalize(user, user_track, session, state_service, study_session)
    if analytics is not None and text != MAIN_MENU:
        await analytics.emit(EVENT_STUDY_COMPLETED, user_id=user.id)
    if query.message:
        await query.message.edit_text(
            text, reply_markup=finished_kb() if text != MAIN_MENU else None
        )
    await query.answer()


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #


async def start_session(
    *,
    query: CallbackQuery,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
    scope: StudyScope,
    scope_ref_id: int | None = None,
) -> None:
    """Reusable session starter — used by the study menu and 'Учить категорию'."""
    studied_today = await ProgressService(session).studied_today_count(
        user.id, current_track, tz_name=user.timezone
    )
    view = await study_session.start(
        user=user,
        user_track=user_track,
        track=current_track,
        scope=scope,
        scope_ref_id=scope_ref_id,
        studied_today=studied_today,
    )
    if view is None:
        await state_service.clear(user.id)
        if query.message:
            await query.message.edit_text(STUDY_NO_WORDS, reply_markup=None)
        await query.answer()
        return

    await state_service.set(user.id, InteractionState.STUDY_ACTIVE)
    await analytics.emit(
        EVENT_STUDY_STARTED,
        user_id=user.id,
        track=current_track.value,
        scope=scope.value,
        words_total=view.total,
    )
    await _render_edit(query, user, view, screen_service, user_track)
    await query.answer()


@router.callback_query(StudyCB.filter(F.action == "start"))
async def on_start(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    try:
        scope = StudyScope(callback_data.scope or StudyScope.GOAL.value)
    except ValueError:
        await query.answer()
        return
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
        scope=scope,
        scope_ref_id=callback_data.scope_ref_id or None,
    )


@router.callback_query(StudyCB.filter(F.action == "answer"))
async def on_quiz_answer(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    view = await study_session.current_view(user.id)
    if view is None:
        await _finish_edit(query, user, user_track, session, state_service, study_session, analytics)
        return
    if view.stage != STAGE_QUIZ or not callback_data.answer.startswith("q"):
        await query.answer(STUDY_USE_BUTTONS)
        return
    try:
        idx = int(callback_data.answer[1:])
    except ValueError:
        await query.answer()
        return
    if idx < 0 or idx >= len(view.options):
        await query.answer()
        return

    correct = view.options[idx] == view.translation
    new_view = await study_session.answer(user.id, correct)
    if new_view is None:
        await _finish_edit(query, user, user_track, session, state_service, study_session, analytics)
        return
    await _render_edit(query, user, new_view, screen_service, user_track)
    await query.answer("✅" if correct else "❌")


@router.message(InState(InteractionState.STUDY_ACTIVE), F.text)
async def on_typing_answer(
    message: Message,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    view = await study_session.current_view(user.id)
    if view is None:
        return
    if view.stage == STAGE_QUIZ:
        await message.answer(STUDY_USE_BUTTONS)
        return

    correct = is_typing_correct(message.text or "", view.writing)
    prefix = STUDY_ANSWER_CORRECT if correct else STUDY_ANSWER_WRONG.format(answer=view.writing)
    new_view = await study_session.answer(user.id, correct)
    if new_view is None:
        text = await _finalize(user, user_track, session, state_service, study_session)
        if text != MAIN_MENU:
            await analytics.emit(EVENT_STUDY_COMPLETED, user_id=user.id)
            await message.answer(f"{prefix}\n\n{text}", reply_markup=finished_kb())
        else:
            await message.answer(text)
        return
    await _render_send(message, user, new_view, screen_service, user_track, prefix=prefix)


@router.callback_query(StudyCB.filter(F.action == "skip"))
async def on_skip(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    new_view = await study_session.skip(user.id)
    if new_view is None:
        await _finish_edit(query, user, user_track, session, state_service, study_session, analytics)
        return
    await _render_edit(query, user, new_view, screen_service, user_track)
    await query.answer("Пропущено")


@router.callback_query(StudyCB.filter(F.action == "hint"))
async def on_hint(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    screen_service: ScreenVersionService,
    study_session: StudySessionService,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    view = await study_session.current_view(user.id)
    if view is None:
        await query.answer()
        return
    # Don't show the example sentence: it usually contains the word itself (or
    # its other forms), which would give the typing answer away. First letter +
    # length is enough of a nudge.
    letters = len((view.writing or "").replace(" ", ""))
    await query.answer(
        f"Начинается с «{view.writing[:1]}…» · букв: {letters}", show_alert=True
    )


@router.callback_query(StudyCB.filter(F.action == "finish"))
async def on_finish(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    await _finish_edit(query, user, user_track, session, state_service, study_session, analytics)


# --------------------------------------------------------------------------- #
# Called from the delete-confirmation flow in my_words.py
# --------------------------------------------------------------------------- #


async def render_current_card(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None = None,
) -> None:
    view = await study_session.current_view(user.id)
    if view is None:
        await _finish_edit(query, user, user_track, session, state_service, study_session)
        return
    await _render_edit(query, user, view, screen_service, user_track)


async def handle_in_study_delete(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None = None,
) -> None:
    new_view = await study_session.delete_current(user.id)
    await state_service.set(user.id, InteractionState.STUDY_ACTIVE)
    if new_view is None:
        await _finish_edit(query, user, user_track, session, state_service, study_session)
        return
    await query.answer("Удалено")
    await _render_edit(query, user, new_view, screen_service, user_track)
