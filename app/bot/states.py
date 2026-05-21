from __future__ import annotations

from enum import StrEnum


class InteractionState(StrEnum):
    IDLE = "idle"
    WAITING_PASSWORD = "waiting_password"
    ONBOARDING_TRACKS = "onboarding_tracks"
    ONBOARDING_DAILY_GOAL = "onboarding_daily_goal"
    ONBOARDING_CUSTOM_GOAL = "onboarding_custom_goal"

    WAITING_MANUAL_WORDS = "waiting_manual_words"
    WAITING_CATEGORY_FOR_WORDS = "waiting_category_for_words"
    WAITING_NEW_CATEGORY_NAME = "waiting_new_category_name"
    WAITING_CATEGORY_RENAME = "waiting_category_rename"

    WAITING_TXT_FILE = "waiting_txt_file"
    WAITING_TXT_CATEGORY = "waiting_txt_category"

    WAITING_DELETE_CONFIRMATION = "waiting_delete_confirmation"

    STUDY_ACTIVE = "study_active"

    PACK_SELECTION = "pack_selection"

    SETTINGS_GOAL_INPUT = "settings_goal_input"
    SETTINGS_PACE_INPUT = "settings_pace_input"


# Universal callback prefixes always allowed regardless of state.
UNIVERSAL_PREFIXES: frozenset[str] = frozenset({"nav", "noop"})

# Per-state allowlist of callback prefixes (in addition to UNIVERSAL_PREFIXES).
STATE_CALLBACK_PREFIXES: dict[InteractionState, frozenset[str]] = {
    InteractionState.IDLE: frozenset({"mm", "mw", "cat", "add", "imp", "pk", "st", "pg", "set", "ob", "qa"}),
    InteractionState.WAITING_PASSWORD: frozenset(),
    InteractionState.ONBOARDING_TRACKS: frozenset({"ob"}),
    InteractionState.ONBOARDING_DAILY_GOAL: frozenset({"ob"}),
    InteractionState.ONBOARDING_CUSTOM_GOAL: frozenset({"ob"}),
    InteractionState.WAITING_MANUAL_WORDS: frozenset({"add"}),
    InteractionState.WAITING_CATEGORY_FOR_WORDS: frozenset({"add", "cat"}),
    InteractionState.WAITING_NEW_CATEGORY_NAME: frozenset({"cat", "add", "imp"}),
    InteractionState.WAITING_CATEGORY_RENAME: frozenset({"cat", "mw"}),
    InteractionState.WAITING_TXT_FILE: frozenset({"imp"}),
    InteractionState.WAITING_TXT_CATEGORY: frozenset({"imp", "cat"}),
    InteractionState.WAITING_DELETE_CONFIRMATION: frozenset({"del", "mw", "st"}),
    InteractionState.STUDY_ACTIVE: frozenset({"st", "del"}),
    InteractionState.PACK_SELECTION: frozenset({"pk", "cat"}),
    InteractionState.SETTINGS_GOAL_INPUT: frozenset({"set"}),
    InteractionState.SETTINGS_PACE_INPUT: frozenset({"set"}),
}


# States that accept text messages (and what kind).
TEXT_ACCEPTING_STATES: frozenset[InteractionState] = frozenset(
    {
        InteractionState.IDLE,  # quick add popup
        InteractionState.WAITING_PASSWORD,
        InteractionState.ONBOARDING_CUSTOM_GOAL,
        InteractionState.WAITING_MANUAL_WORDS,
        InteractionState.WAITING_NEW_CATEGORY_NAME,
        InteractionState.WAITING_CATEGORY_RENAME,
        InteractionState.SETTINGS_GOAL_INPUT,
        InteractionState.STUDY_ACTIVE,  # typing-stage answers
    }
)


# States that accept document uploads.
DOCUMENT_ACCEPTING_STATES: frozenset[InteractionState] = frozenset(
    {InteractionState.WAITING_TXT_FILE}
)
