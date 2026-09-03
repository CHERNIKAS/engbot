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


# How big the active pool may get, derived from how much the user actually
# answers instead of from a number they picked once. `pace × 3` ignored their
# real throughput, and prod showed exactly what that costs:
#
#   user  active  answers/day  days per word  mastered
#     1      63       8.9          ~7            17
#     3      22      13.9          ~1.6          37
#     2      20       3.9          ~5             4
#
# User 3 answers less in total than user 1 and has mastered twice as many words
# — a word only sticks if it comes back before it's forgotten, and the pool size
# is what decides that. 1.5 answers-per-day per active word is user 3's ratio,
# the one shape in prod that demonstrably works.
THROUGHPUT_TO_POOL = 1.5
MIN_POOL = 5  # below this a beginner would run dry between cards
MAX_POOL = 40  # above this even a heavy user can't cycle the pool
# What to assume before there's enough history to measure. Deliberately modest:
# starting small and growing is recoverable, starting huge is the bug above.
DEFAULT_THROUGHPUT = 6.0


def pool_ceiling(answers_per_day: float | None) -> int:
    """Max words in flight for a user answering this much per day."""
    rate = DEFAULT_THROUGHPUT if not answers_per_day or answers_per_day <= 0 else answers_per_day
    return max(MIN_POOL, min(MAX_POOL, round(rate * THROUGHPUT_TO_POOL)))


def label_for(pace: int) -> str:
    """Human label like '🚶 Ровно' for the current pace (falls back to default)."""
    for value, emoji, name in PACE_OPTIONS:
        if value == pace:
            return f"{emoji} {name}"
    return f"{pace}"
