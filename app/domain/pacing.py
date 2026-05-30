from __future__ import annotations

# Pure helpers for the new-word intake pace ("сколько новых слов в день").
#
# We decouple INTRODUCING new words from MASTERING old ones (the old rule —
# "a new word enters only when an old one hits 10-in-a-row" — gated growth on
# the slowest possible signal). Mature SRS (Anki/FSRS) instead use two
# independent dials: a daily new-card cap + a review-load ceiling. Here:
#
#   • pace      = new words introduced per day (user-chosen)
#   • ceiling   = max words "in flight" at once = pace × POOL_CEILING_MULT
#
# A new word is introduced only while BOTH gates pass: today's intake < pace
# AND the active pool < ceiling. That lets the user grow fast without the pool
# ballooning into mush (push would otherwise cycle a huge pool too rarely).

# (value, key, emoji, label) — shown in the pace picker.
PACE_OPTIONS: tuple[tuple[int, str, str], ...] = (
    (3, "🐢", "Спокойно"),
    (7, "🚶", "Ровно"),
    (15, "🏃", "Бодро"),
    (25, "🔥", "Жёстко"),
)
PACE_VALUES: tuple[int, ...] = tuple(v for v, _, _ in PACE_OPTIONS)
DEFAULT_PACE = 7
POOL_CEILING_MULT = 3

_SETTINGS_KEY = "new_pace"


def pace_of(settings: dict | None) -> int:
    """Read the user's chosen pace from user_track.settings, clamped to a known
    option (defends against stale/garbage values)."""
    raw = (settings or {}).get(_SETTINGS_KEY, DEFAULT_PACE)
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PACE
    return val if val in PACE_VALUES else DEFAULT_PACE


def ceiling_of(pace: int) -> int:
    """Max words active ('in flight') at once for a given pace."""
    return max(1, pace) * POOL_CEILING_MULT


def label_for(pace: int) -> str:
    """Human label like '🚶 Ровно' for the current pace (falls back to default)."""
    for value, emoji, name in PACE_OPTIONS:
        if value == pace:
            return f"{emoji} {name}"
    return f"{pace}"
