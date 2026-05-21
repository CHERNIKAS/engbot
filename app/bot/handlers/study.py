from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import StudyCB
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.study import (
    classic_answer_kb,
    classic_question_kb,
    finished_kb,
    quiz_kb,
)
from app.bot.states import InteractionState
from app.bot.texts import (
    MAIN_MENU,
    STUDY_CARD_NO_TRANSLATION,
    STUDY_EXAMPLE_MISSING,
    STUDY_FINISHED,
    STUDY_NO_WORDS,
)
from app.domain.enums import LearningTrack, ReviewResult, StudyMode, StudyScope
from app.domain.models import User, UserTrack
from app.services.analytics import EVENT_STUDY_COMPLETED, EVENT_STUDY_STARTED, Analytics
from app.services.interaction_state_service import InteractionStateService
from app.services.progress_service import ProgressService
from app.services.screen_service import ScreenVersionService
from app.services.study_session_service import StudySessionService
from app.services.user_track_service import UserTrackService

router = Router(name="study")

SCREEN_KIND = "study_card"


def _is_japanese(track: str | None) -> bool:
    return track == LearningTrack.JAPANESE.value


def _card_text_question(card: dict, current: int, total: int, track: str | None) -> str:
    writing = card.get("writing", "")
    if _is_japanese(track):
        # For Japanese we show writing (kanji/kana) only on the question side.
        return f"<b>{writing}</b>\n\n<i>Карточка {current}/{total}</i>"
    return f"<b>{writing}</b>\n\n<i>Карточка {current}/{total}</i>"


def _card_text_revealed(
    card: dict, current: int, total: int, track: str | None, romaji_enabled: bool
) -> str:
    writing = card.get("writing", "")
    translation = card.get("translation") or STUDY_CARD_NO_TRANSLATION
    if _is_japanese(track):
        lines = [f"<b>{writing}</b>"]
        if card.get("kana") and card["kana"] != writing:
            lines.append(f"<i>{card['kana']}</i>")
        if romaji_enabled and card.get("romaji"):
            lines.append(f"<code>{card['romaji']}</code>")
        lines.append("")
        lines.append(translation)
        lines.append("")
        lines.append(f"<i>Карточка {current}/{total}</i>")
        return "\n".join(lines)
    return f"<b>{writing}</b>\n\n{translation}\n\n<i>Карточка {current}/{total}</i>"


def _quiz_text(card: dict, current: int, total: int, track: str | None) -> str:
    writing = card.get("writing", "")
    if _is_japanese(track):
        kana = card.get("kana")
        prompt = writing if not kana or kana == writing else f"{writing} ({kana})"
    else:
        prompt = writing
    return f"Что значит <b>{prompt}</b>?\n\n<i>Карточка {current}/{total}</i>"


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
    mode: StudyMode,
    scope: StudyScope,
    scope_ref_id: int | None = None,
) -> None:
    progress = ProgressService(session)
    studied_today = await progress.studied_today_count(user.id, current_track, tz_name=user.timezone)
    snap = await study_session.start(
        user=user,
        user_track=user_track,
        track=current_track,
        mode=mode,
        scope=scope,
        scope_ref_id=scope_ref_id,
        studied_today=studied_today,
    )
    if snap is None:
        await state_service.clear(user.id)
        from app.services.user_track_service import UserTrackService as _UTS  # noqa
        if query.message:
            await query.message.edit_text(STUDY_NO_WORDS, reply_markup=None)
        await query.answer()
        return

    await state_service.set(user.id, InteractionState.STUDY_ACTIVE)
    await analytics.emit(
        EVENT_STUDY_STARTED,
        user_id=user.id,
        track=current_track.value,
        mode=mode.value,
        scope=scope.value,
        words_total=len(snap.cards),
    )
    await render_current_card(
        query=query,
        user=user,
        session=session,
        state_service=state_service,
        study_session=study_session,
        screen_service=screen_service,
    )


def _romaji_enabled(user_track: UserTrack | None) -> bool:
    if user_track is None:
        return True
    return bool((user_track.settings or {}).get("romaji_enabled", True))


async def render_current_card(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None = None,
) -> None:
    snap = await study_session.get(user.id)
    if snap is None or snap.index >= len(snap.cards):
        await finish_and_render(query, user, session, state_service, study_session)
        return

    card = snap.cards[snap.index]
    total = len(snap.cards)
    current = snap.index + 1
    version = await screen_service.bump(user.id, SCREEN_KIND)
    romaji = _romaji_enabled(user_track)
    track = snap.track
    user_word_id = card.get("user_word_id", 0)

    if snap.mode == StudyMode.QUIZ.value:
        options = snap.quiz_options.get(str(user_word_id))
        if not options:
            text = _card_text_question(card, current, total, track)
            if query.message:
                await query.message.edit_text(
                    text,
                    reply_markup=classic_question_kb(user_word_id, version),
                    parse_mode="HTML",
                )
            return
        text = _quiz_text(card, current, total, track)
        if query.message:
            await query.message.edit_text(
                text,
                reply_markup=quiz_kb(options, version, user_word_id),
                parse_mode="HTML",
            )
        return

    revealed = snap.revealed.get(str(snap.index), False)
    if revealed:
        text = _card_text_revealed(card, current, total, track, romaji)
        kb = classic_answer_kb(user_word_id, version)
    else:
        text = _card_text_question(card, current, total, track)
        kb = classic_question_kb(user_word_id, version)

    if query.message:
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def finish_and_render(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    current_track: LearningTrack | None = None,
) -> None:
    snap = await study_session.finish(user.id)
    progress = ProgressService(session)
    await progress.update_streak(user)
    await state_service.clear(user.id)

    if snap is None:
        if query.message:
            await query.message.edit_text(MAIN_MENU, reply_markup=None)
        await query.answer()
        return

    text = STUDY_FINISHED.format(
        correct=snap.correct,
        wrong=snap.wrong,
        total=snap.correct + snap.wrong,
    )
    if query.message:
        await query.message.edit_text(text, reply_markup=finished_kb())
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
        mode = StudyMode(callback_data.mode or StudyMode.CLASSIC.value)
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
        mode=mode,
        scope=scope,
        scope_ref_id=callback_data.scope_ref_id or None,
    )


async def _check_screen(query: CallbackQuery, user_id: int, screen_service: ScreenVersionService, version: str) -> bool:
    if not await screen_service.check(user_id, SCREEN_KIND, version):
        await query.answer("Это действие уже устарело.", show_alert=False)
        return False
    return True


@router.callback_query(StudyCB.filter(F.action == "show_translation"))
async def on_show_translation(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    await study_session.reveal_translation(user.id)
    await render_current_card(query, user, session, state_service, study_session, screen_service, user_track=user_track)
    await query.answer()


@router.callback_query(StudyCB.filter(F.action == "example"))
async def on_example(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    screen_service: ScreenVersionService,
    study_session: StudySessionService,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    card = await study_session.current_card(user.id)
    if card is None or not card.example:
        await query.answer(STUDY_EXAMPLE_MISSING, show_alert=True)
        return
    await query.answer(card.example, show_alert=True)


@router.callback_query(StudyCB.filter(F.action == "skip"))
async def on_skip(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    snap = await study_session.skip(user.id)
    if snap is None or study_session.is_complete(snap):
        await finish_and_render(query, user, session, state_service, study_session, current_track)
        return
    await render_current_card(query, user, session, state_service, study_session, screen_service, user_track=user_track)
    await query.answer()


@router.callback_query(StudyCB.filter(F.action == "answer"))
async def on_answer(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    user_track: UserTrack,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    snap = await study_session.get(user.id)
    if snap is None:
        await query.answer()
        return

    if snap.mode == StudyMode.QUIZ.value:
        if not callback_data.answer.startswith("q"):
            await query.answer()
            return
        try:
            idx = int(callback_data.answer[1:])
        except ValueError:
            await query.answer()
            return
        card = await study_session.current_card(user.id)
        if card is None:
            await query.answer()
            return
        options = snap.quiz_options.get(str(card.user_word_id)) or []
        if idx < 0 or idx >= len(options):
            await query.answer()
            return
        is_correct = options[idx] == card.translation
        result = ReviewResult.CORRECT if is_correct else ReviewResult.WRONG
    else:
        try:
            result = ReviewResult(callback_data.answer)
        except ValueError:
            await query.answer()
            return

    new_snap = await study_session.answer(user, user_track, result)
    if new_snap is None or study_session.is_complete(new_snap):
        await finish_and_render(query, user, session, state_service, study_session, current_track)
        return
    await render_current_card(query, user, session, state_service, study_session, screen_service, user_track=user_track)
    await query.answer("✓" if result in (ReviewResult.EASY, ReviewResult.NORMAL, ReviewResult.CORRECT) else "")


@router.callback_query(StudyCB.filter(F.action == "finish"))
async def on_finish(
    query: CallbackQuery,
    callback_data: StudyCB,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    analytics: Analytics,
) -> None:
    if not await _check_screen(query, user.id, screen_service, callback_data.v):
        return
    snap = await study_session.get(user.id)
    if snap is not None:
        await analytics.emit(
            EVENT_STUDY_COMPLETED,
            user_id=user.id,
            track=snap.track,
            correct=snap.correct,
            wrong=snap.wrong,
            total=snap.correct + snap.wrong,
        )
    await finish_and_render(query, user, session, state_service, study_session, current_track)


async def handle_in_study_delete(
    query: CallbackQuery,
    user: User,
    session: AsyncSession,
    state_service: InteractionStateService,
    study_session: StudySessionService,
    screen_service: ScreenVersionService,
    user_track: UserTrack | None = None,
) -> None:
    snap = await study_session.delete_current(user.id)
    await state_service.set(user.id, InteractionState.STUDY_ACTIVE)
    if snap is None or study_session.is_complete(snap):
        await finish_and_render(query, user, session, state_service, study_session)
        return
    await query.answer("Удалено.")
    await render_current_card(query, user, session, state_service, study_session, screen_service, user_track=user_track)
