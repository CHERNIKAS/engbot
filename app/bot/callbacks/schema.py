from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


# Navigation — always allowed.
class NavCB(CallbackData, prefix="nav"):
    action: str  # home | back | cancel


class NoopCB(CallbackData, prefix="noop"):
    tag: str = "_"


# Onboarding.
class OnboardingCB(CallbackData, prefix="ob"):
    action: str  # start | toggle_track | tracks_done | goal | custom | seed_skip | done
    #          | lvl_start | lvl | lvl_skip  (placement test; lvl value -1 = "не знаю")
    value: int = 0
    track: str = ""  # for action == "toggle_track"


# Main menu.
class MainMenuCB(CallbackData, prefix="mm"):
    section: str  # words | study | add | import | packs | progress | settings | track
    value: str = ""  # for section == "track" — LearningTrack value


# My words / categories list browsing.
class MyWordsCB(CallbackData, prefix="mw"):
    action: str  # open | list | study_cat | manage | word
    category_id: int = 0  # 0 = all, -1 = uncategorized, >0 = specific
    page: int = 0
    user_word_id: int = 0  # for action == "word" (open a word's detail card)


# Categories CRUD + management.
class CategoryCB(CallbackData, prefix="cat"):
    action: str  # pick | new | manage | rename | del_ask | del_confirm | move | merge | move_to | merge_to
    category_id: int = 0
    flow: str = ""  # which flow invoked us: add | imp | mw
    v: str = ""  # screen version — checked on destructive actions
    target_id: int = 0  # move/merge destination (-1 = «Без категории», >0 = category)


# Add words flow.
class AddWordsCB(CallbackData, prefix="add"):
    action: str  # start | choose_cat | confirm | more


# TXT import flow.
class ImportCB(CallbackData, prefix="imp"):
    action: str  # start | confirm | choose_cat | prioritise
    category_id: int = 0
    v: str = ""  # screen version


# Packs browser (ReWord-style checklist).
class PacksCB(CallbackData, prefix="pk"):
    action: str  # menu | toggle | page | reset | add | rem_ok
    category: str = ""
    pack_id: int = 0
    page: int = 0
    v: str = ""  # screen version — checked on rem_ok (destructive removal)


# Study session.
class StudyCB(CallbackData, prefix="st"):
    action: str  # menu | start | show_translation | answer | example | skip | delete | finish
    mode: str = ""
    scope: str = ""
    scope_ref_id: int = 0
    answer: str = ""
    v: str = ""  # screen version


# Progress.
class ProgressCB(CallbackData, prefix="pg"):
    action: str = "open"  # open | managed | unarchive | unsnooze | backlog | park


# Settings.
class SettingsCB(CallbackData, prefix="set"):
    action: str  # open | goal | goal_value | pace | pace_value | push_open | push_win | push_win_set | newpace | newpace_set
    #          | tz_open | tz_set | level | level_test  (level = show CEFR level, level_test = retake it)
    value: str = ""
    v: str = ""  # screen version — checked on goal_value / pace_value


# Delete confirmation.
class DeleteCB(CallbackData, prefix="del"):
    action: str  # ask | confirm | cancel
    user_word_id: int = 0
    flow: str = ""  # mw | st
    v: str = ""  # screen version — checked on confirm


# Quick add popup (idle text).
class QuickAddCB(CallbackData, prefix="qa"):
    action: str  # add | choose_cat | cancel
    token: str = ""


# Guided course ("🎓 Курс").
class CourseCB(CallbackData, prefix="cr"):
    action: str  # open | start | pause | map


# Search across my words + catalog.
class SearchCB(CallbackData, prefix="sr"):
    action: str  # open | add
    word_id: int = 0  # for action == "add" (catalog word → my vocabulary)


# Push-learning card answer.
class PushCB(CallbackData, prefix="pu"):
    action: str  # ans | giveup | know | hide | master | snooze | rule | rule_ok | leech_park | leech_keep | unarchive | unsnooze
    uw_id: int = 0
    idx: int = 0
    days: int = 0  # snooze duration for action == "snooze"
