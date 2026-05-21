from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.schema import ProgressCB
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.texts import PROGRESS_TITLE
from app.domain.enums import LearningTrack, TRACK_LABELS
from app.domain.models import User
from app.services.progress_service import ProgressService
from app.services.user_track_service import UserTrackService

router = Router(name="progress")


@router.callback_query(ProgressCB.filter(F.action == "open"))
async def on_progress_open(
    query: CallbackQuery,
    user: User,
    current_track: LearningTrack,
    session: AsyncSession,
    user_track_service: UserTrackService,
) -> None:
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
    if query.message:
        await query.message.edit_text(text, reply_markup=None, parse_mode="HTML")
    await query.answer()
