from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)
    # Default to Moscow (UTC+3) — the bot's audience is RU-speaking, so UTC is
    # the wrong default (push window/streak would be hours off). Users can pick
    # their own zone in Settings → 🕐 Часовой пояс.
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    # CEFR level from the placement test. NULL = not placed yet, which is a real
    # state, not a missing default: the picker falls back to a safe level while
    # the test stays offerable. See app/domain/levels.py.
    level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Global streak — shared across all learning tracks.
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_study_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserTrack(Base):
    """Per-user per-track settings (daily goal, pace, romaji toggle, etc.)."""
    __tablename__ = "user_tracks"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    track: Mapped[str] = mapped_column(String(8), primary_key=True)
    daily_goal_words: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    learning_pace: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("daily_goal_words BETWEEN 1 AND 100", name="ck_user_tracks_goal_range"),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "track", "name", name="uq_categories_user_track_name"),
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    # Generic displayable form — for English it's the English word, for Japanese the kanji/kana writing.
    writing: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_word: Mapped[str] = mapped_column(String(128), nullable=False)
    translation: Mapped[str | None] = mapped_column(String(256), nullable=True)
    transcription: Mapped[str | None] = mapped_column(String(128), nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Abstract context example shown ON the push card as a hint. Uses a synonym
    # / paraphrase so the target word itself isn't in the sentence — visible
    # context without spoiling the answer. Paired Russian translation rides
    # under it. Both nullable: when an abstract version can't be authored
    # cleanly we just skip the example on that word's card.
    abstract_example_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract_example_ru: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Japanese-specific (nullable for English rows).
    kana: Mapped[str | None] = mapped_column(String(128), nullable=True)
    romaji: Mapped[str | None] = mapped_column(String(128), nullable=True)
    script_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # How common the word is in everyday English: 1 = top-thousand .. 5 = rare
    # or a narrow term. Pairs with `level` to order what gets taught next —
    # level alone puts "plummet" and "often" in the same bucket too easily.
    freq_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Articles and auxiliary contractions: real words, but unusable as a
    # "pick the translation" card — every honest distractor differs only by
    # tense or number. Excluded from word selection; grammar teaches them.
    is_function_word: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Corpus rank, 1 = most common. NULL means off-list, which is not the same
    # as "rare" — see app/domain/ngsl.py. Order with NULLS LAST.
    ngsl_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Senses unrelated enough that one translation teaches one of them as if it
    # were the whole word (`charge`, `stock`, `firm`). Still worth teaching —
    # they are frequent — but the queue prefers unambiguous words of the same
    # band first, so the learner meets them with more context behind them.
    polysemous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # A form of some other entry — `drove` for `drive`, `better` for `good`.
    # Real knowledge, but the form itself is the lesson, so the irregular-verb
    # and comparatives topics teach it and the word rotation skips it.
    is_inflection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # A phrasebook entry, learned whole. Has no corpus rank, so leaving it in
    # the word queue sorts it behind every ranked word there is; it gets its own
    # stream instead. Not the same as "spelled with a space" — `post office` is
    # an ordinary word.
    is_phrase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # A phrase's colloquial rendering («Come again?» beside «Could you repeat
    # that?») and a few words on its tone; NULL when there is none worth it.
    colloquial: Mapped[str | None] = mapped_column(Text, nullable=True)
    colloquial_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deliberately withheld from teaching — vulgar, interjections, anything the
    # owner decided should not be a card. Separate from `is_function_word`,
    # which means "grammar teaches this instead": these are not taught anywhere.
    # A flag rather than a delete, so the decision is visible and reversible and
    # nobody's progress on the word disappears with the row.
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Coarse part of speech ('verb' | 'noun' | 'adj'), used to pick quiz
    # distractors of the same kind. Nullable: not every word can be tagged.
    part_of_speech: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("track", "normalized_word", name="uq_words_track_normalized"),
    )


class UserWord(Base):
    __tablename__ = "user_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    custom_translation: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # For a phrase with a colloquial rendering: neutral / casual / both, as the
    # learner chose. NULL until they are asked.
    phrase_style: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    # "Teach this one first" — set by the user on their own imports. Ordered
    # ahead of level fit, because a list someone assembled for a deadline is
    # about their intent, not the catalogue's idea of difficulty.
    priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False, index=True)
    ease_score: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    repetitions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistakes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Weighted credit toward "learned". Unlike repetitions_count it values a
    # typed answer above a guessable four-option one — see app/domain/mastery.py.
    learning_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Correct TYPED answers. The gate guessing can't pass: a word never reaches
    # mastery on choice cards alone, however high its score climbs.
    production_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Push v2: 0–5 health score for mastered words (5.0 = fully learned).
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Consecutive wrong answers (reset to 0 on any correct). Powers leech
    # detection: when it hits the threshold the bot offers to postpone the word
    # so one impossible word can't permanently clog the active pool.
    consecutive_wrong: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Archived ("я знаю" / "перестать показывать") — out of all push rotation,
    # restorable from the management menu. Snoozed words hide until snooze_until.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word"),
        Index("ix_user_words_user_track_next_review", "user_id", "track", "next_review_at"),
        Index("ix_user_words_user_track_status", "user_id", "track", "status"),
    )


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Teaching order within a category. Insertion order used to stand in for
    # this, which silently put the phrasal-verbs pack ahead of «How are you?»
    # purely because it was created first.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    words_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Who may edit this pack: "migration" or "admin". A pack edited through the
    # admin moves to "admin" and migrations stop touching it — otherwise a hand
    # fix disappears on the next deploy, or a shipped fix is reverted by a stale
    # hand edit, and neither leaves a trace.
    origin: Mapped[str] = mapped_column(String(16), default="migration", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PackWord(Base):
    __tablename__ = "pack_words"

    pack_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packs.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    words_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WordReview(Base):
    __tablename__ = "word_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_words.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("study_sessions.id", ondelete="SET NULL"), nullable=True
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    # How long the card took, and how many pushes it took to get answered. Only
    # attempts == 1 rows time actual attention — see migration 0044.
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_word_reviews_user_word_reviewed", "user_word_id", "reviewed_at"),
        Index("ix_word_reviews_user_track_date", "user_id", "track", "reviewed_at"),
    )


class GrammarReview(Base):
    """One grammar answer, logged like WordReview so daily-activity counts
    include grammar (word_reviews FK is word-only, so grammar needs its own log)."""
    __tablename__ = "grammar_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_grammar_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_grammar_items.id", ondelete="CASCADE"), nullable=False
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_grammar_reviews_user_track_date", "user_id", "track", "reviewed_at"),
    )


class DayPlan(Base):
    """Today's list of cards — composed once, then held until it is closed.

    Not in Redis with the rest of the push state, because a plan is explicitly
    allowed to outlive its day: an unfinished one is not replaced tomorrow, it
    is the same plan until closed. An eviction mid-way would hand the learner a
    different day, which is the unpredictability this replaces.

    `items` is `[{"kind": ..., "ref": int, "done": bool}]`. Kinds are the
    constants in `app.domain.day_plan`. Storing the composition instead of
    recomputing it is the point: recomputation would let the plan shift
    underneath whenever the review queue moved.
    """
    __tablename__ = "day_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # The push day it was opened for — rolls at the start of the user's window,
    # not at midnight, so it is not always the calendar date.
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_day_plans_user_open", "user_id", "track", "closed_at"),
        Index(
            "uq_day_plans_one_open",
            "user_id",
            "track",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    props: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class GrammarTopic(Base):
    """A grammar lesson: a rule + a set of choose-the-form exercises. Delivered
    inside the course/push, choice-only (no typing)."""
    __tablename__ = "grammar_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    track: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GrammarItem(Base):
    """One exercise: a sentence with a gap, the correct option, and distractors.
    Options shown = [correct, *distractors], shuffled at render."""
    __tablename__ = "grammar_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[str] = mapped_column(String(64), nullable=False)
    distractors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GrammarPhrase(Base):
    """One sentence to construct: the Russian, the English, and the English cut
    into decision points.

    Gap-fill cards cannot prove a tense is known — four options give a 25% floor
    from guessing alone. Here there is nothing to pick from in the typing mode,
    and in the assisted mode `slots` supports without giving away: after «She»
    the learner still has to know it takes «doesn't», and elimination will not
    tell them.

    `alternatives` holds the other correct renderings, so writing «does not»
    instead of «doesn't» is never marked wrong.
    """
    __tablename__ = "grammar_phrases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ru: Mapped[str] = mapped_column(Text, nullable=False)
    en: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # [{"correct": "She", "options": ["She", "They", "I"]}, ...] — concatenating
    # every `correct` reproduces `en` exactly; migration 0055 verifies it.
    slots: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)



class UserGrammarItem(Base):
    """Per-user spaced-repetition progress on a grammar exercise — mirrors the
    UserWord fields so apply_review() works on it unchanged."""
    __tablename__ = "user_grammar_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    grammar_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_items.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False, index=True)
    ease_score: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    repetitions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistakes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "grammar_item_id", name="uq_user_grammar_item"),
        Index("ix_user_grammar_items_user_status", "user_id", "status"),
    )


class UserGrammarTopic(Base):
    """A learner's standing in one grammar topic.

    `score` decays toward recent answers rather than accumulating, so it can
    fall — an average over per-exercise progress only ever climbs, which is how
    a topic passed months ago would still show full marks today.

    `typing` is a ratchet, not a toggle. The mode switches from tapping pieces
    to free typing once the score is high enough, and must not switch back: the
    harder mode drops the score, which would otherwise push it under the
    threshold and bounce the learner between modes indefinitely.

    `recent` is the last handful of phrase ids, so the same few sentences are
    not what gets memorised in place of the rule.
    """
    __tablename__ = "user_grammar_topics"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_topics.id", ondelete="CASCADE"), primary_key=True
    )
    # Shown once, before the topic's exercises.
    rule_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 0..1; the card shows it as 0..5. Starts at zero and climbs, which is
    # honest — nothing has been demonstrated yet.
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    typing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recent: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # The score alone cannot tell "bad at this" from "has answered twice".
    answered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Consecutive passed checks, driving the expanding interval between them.
    held_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Stored rather than derived: the interval depends on the streak at the
    # time, so recomputing later would move a date already promised.
    test_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_user_grammar_topics_active", "user_id", "passed_at"),
        Index("ix_user_grammar_topics_test_due", "user_id", "test_due_at"),
    )
