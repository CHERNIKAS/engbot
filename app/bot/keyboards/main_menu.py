from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import MainMenuCB
from app.config import get_settings
from app.domain.enums import LearningTrack, TRACK_LABELS, enabled_tracks
from app.domain.models import UserTrack


def _track_switcher_row(
    active_tracks: list[UserTrack],
    current_track: LearningTrack,
    allowed: list[LearningTrack],
) -> list[InlineKeyboardButton]:
    allowed_set = set(allowed)
    visible: list[UserTrack] = []
    for ut in active_tracks:
        try:
            t = LearningTrack(ut.track)
        except ValueError:
            continue
        if t in allowed_set:
            visible.append(ut)
    if len(visible) <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    for ut in visible:
        t = LearningTrack(ut.track)
        marker = "• " if t == current_track else ""
        row.append(
            InlineKeyboardButton(
                text=f"{marker}{TRACK_LABELS[t]}",
                callback_data=MainMenuCB(section="track", value=t.value).pack(),
            )
        )
    return row


def main_menu_kb(
    active_tracks: list[UserTrack] | None = None,
    current_track: LearningTrack | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if active_tracks and current_track is not None:
        allowed = enabled_tracks(get_settings().enable_japanese)
        switcher = _track_switcher_row(active_tracks, current_track, allowed)
        if switcher:
            rows.append(switcher)
    rows.extend(
        [
            [
                InlineKeyboardButton(text="📚 Мои слова", callback_data=MainMenuCB(section="words").pack()),
                InlineKeyboardButton(text="🔥 Учить", callback_data=MainMenuCB(section="study").pack()),
            ],
            [
                InlineKeyboardButton(text="➕ Добавить слова", callback_data=MainMenuCB(section="add").pack()),
                InlineKeyboardButton(text="📂 Импорт TXT", callback_data=MainMenuCB(section="import").pack()),
            ],
            [
                InlineKeyboardButton(text="📦 Паки", callback_data=MainMenuCB(section="packs").pack()),
                InlineKeyboardButton(text="📊 Прогресс", callback_data=MainMenuCB(section="progress").pack()),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data=MainMenuCB(section="settings").pack()),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
