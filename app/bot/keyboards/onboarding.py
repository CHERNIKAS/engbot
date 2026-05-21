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


def daily_goal_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="5", callback_data=OnboardingCB(action="goal", value=5).pack()),
            InlineKeyboardButton(text="10", callback_data=OnboardingCB(action="goal", value=10).pack()),
            InlineKeyboardButton(text="20", callback_data=OnboardingCB(action="goal", value=20).pack()),
            InlineKeyboardButton(text="50", callback_data=OnboardingCB(action="goal", value=50).pack()),
        ],
        [
            InlineKeyboardButton(text="✍️ Ввести своё", callback_data=OnboardingCB(action="custom").pack())
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
