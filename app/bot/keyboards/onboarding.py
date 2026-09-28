from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.schema import OnboardingCB
from app.domain.enums import LearningTrack, TRACK_LABELS


def onboarding_intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать ▶️", callback_data=OnboardingCB(action="start").pack())]
        ]
    )


def tracks_picker_kb(
    selected: set[LearningTrack],
    allowed: list[LearningTrack] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    tracks = allowed if allowed is not None else list(LearningTrack)
    for t in tracks:
        marker = "✅" if t in selected else "☑️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker} {TRACK_LABELS[t]}",
                    callback_data=OnboardingCB(action="toggle_track", track=t.value).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Продолжить ▶️",
                callback_data=OnboardingCB(action="tracks_done").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def onboarding_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="В меню ▶️", callback_data=OnboardingCB(action="done").pack())]
        ]
    )
