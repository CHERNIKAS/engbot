from __future__ import annotations

from enum import StrEnum


class LearningTrack(StrEnum):
    ENGLISH = "en"
    JAPANESE = "ja"


TRACK_LABELS: dict[LearningTrack, str] = {
    LearningTrack.ENGLISH: "🇺🇸 English",
    LearningTrack.JAPANESE: "🇯🇵 Japanese",
}


def enabled_tracks(enable_japanese: bool) -> list[LearningTrack]:
    """Returns the list of tracks the UI may surface, gated by feature flags."""
    out = [LearningTrack.ENGLISH]
    if enable_japanese:
        out.append(LearningTrack.JAPANESE)
    return out


class ScriptType(StrEnum):
    LATIN = "latin"
    HIRAGANA = "hiragana"
    KATAKANA = "katakana"
    KANJI = "kanji"
    MIXED = "mixed"


class LearningPace(StrEnum):
    CHILL = "chill"
    NORMAL = "normal"
    INTENSIVE = "intensive"
    HARDCORE = "hardcore"


PACE_INTERVAL_MULTIPLIER: dict[LearningPace, float] = {
    LearningPace.CHILL: 1.3,
    LearningPace.NORMAL: 1.0,
    LearningPace.INTENSIVE: 0.8,
    LearningPace.HARDCORE: 0.6,
}


PACE_NEW_WORDS_PER_SESSION: dict[LearningPace, int] = {
    LearningPace.CHILL: 3,
    LearningPace.NORMAL: 6,
    LearningPace.INTENSIVE: 10,
    LearningPace.HARDCORE: 15,
}


class WordStatus(StrEnum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"


class WordSource(StrEnum):
    MANUAL = "manual"
    TXT_IMPORT = "txt_import"
    PACK = "pack"


class CategoryType(StrEnum):
    USER = "user"
    PACK_CATEGORY = "pack_category"


class StudyMode(StrEnum):
    CLASSIC = "classic"
    QUIZ = "quiz"
    TYPING = "typing"


class StudyScope(StrEnum):
    GOAL = "goal"
    ALL = "all"
    CATEGORY = "category"
    WEAK = "weak"
    NEW = "new"
    QUICK = "quick"


class ReviewResult(StrEnum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    CORRECT = "correct"
    WRONG = "wrong"
