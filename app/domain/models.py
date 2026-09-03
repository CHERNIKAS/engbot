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
    String,
    Text,
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
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False, index=True)
    ease_score: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    repetitions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistakes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
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
    words_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_grammar_reviews_user_track_date", "user_id", "track", "reviewed_at"),
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
    """Tracks that the user has been shown a topic's rule card (so we show it
    once, before its exercises)."""
    __tablename__ = "user_grammar_topics"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_topics.id", ondelete="CASCADE"), primary_key=True
    )
    rule_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
