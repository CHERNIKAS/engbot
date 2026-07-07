from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.texts import (
    DIGEST_ACCURACY,
    DIGEST_HARDEST,
    DIGEST_MASTERED,
    DIGEST_MASTERED_DELTA,
    DIGEST_OUTRO,
    DIGEST_STREAK,
    DIGEST_TITLE,
)
from app.config import get_settings
from app.domain.enums import LearningTrack, ReviewResult, WordStatus
from app.domain.models import GrammarReview, UserWord, Word, WordReview
from app.infrastructure.repositories.user_tracks import UserTrackRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.users import UserRepository
from app.logging_setup import get_logger
from app.services.progress_service import _plural
from app.services.user_track_service import UserTrackService

log = get_logger("digest")

_TRACK = LearningTrack.ENGLISH
_SENT_KEY = "digest:{user_id}:{week}"
_SENT_TTL = 700_000  # ~8 days — one digest per ISO week
_MIN_ANSWERS = 5  # quieter weeks don't earn a digest
_HARDEST_MIN_WRONG = 2


@dataclass
class WeekStats:
    words_correct: int
    words_wrong: int
    grammar_correct: int
    grammar_wrong: int
    mastered_total: int
    mastered_delta: int | None  # None = first digest, no snapshot to diff against
    streak_days: int
    hardest: tuple[str, int] | None  # (writing, wrong count) — the week's toughest word

    @property
    def answers(self) -> int:
        return self.words_correct + self.words_wrong + self.grammar_correct + self.grammar_wrong

    @property
    def accuracy(self) -> int:
        total = self.answers
        if total == 0:
            return 0
        return round(100 * (self.words_correct + self.grammar_correct) / total)


def format_digest(stats: WeekStats) -> str:
    """Render the weekly digest message (pure, unit-testable)."""
    lines = [
        DIGEST_TITLE,
        DIGEST_ACCURACY.format(
            answers=stats.answers,
            answers_word=_plural(stats.answers, "ответ", "ответа", "ответов"),
            words=stats.words_correct + stats.words_wrong,
            grammar=stats.grammar_correct + stats.grammar_wrong,
            accuracy=stats.accuracy,
        ),
    ]
    if stats.mastered_delta is not None and stats.mastered_delta > 0:
        lines.append(
            DIGEST_MASTERED_DELTA.format(delta=stats.mastered_delta, total=stats.mastered_total)
        )
    else:
        lines.append(DIGEST_MASTERED.format(total=stats.mastered_total))
    if stats.streak_days > 0:
        lines.append(
            DIGEST_STREAK.format(
                streak=stats.streak_days,
                days_word=_plural(stats.streak_days, "день", "дня", "дней"),
            )
        )
    if stats.hardest is not None:
        writing, wrongs = stats.hardest
        lines.append(
            DIGEST_HARDEST.format(
                word=writing,
                wrongs=wrongs,
                wrongs_word=_plural(wrongs, "промах", "промаха", "промахов"),
            )
        )
    lines.append("")
    lines.append(DIGEST_OUTRO)
    return "\n".join(lines)


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class DigestService:
    """Once a week the bot finally talks back: a short recap of the user's week
    (answers, accuracy, newly mastered words, the toughest word). The bot asks
    questions all day long — this is the only place it reports the score."""

    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot

    async def run(self) -> int:
        settings = get_settings()
        if not settings.digest_enabled:
            return 0
        now = datetime.now(timezone.utc)
        users = await UserRepository(self._session).list_for_push()
        ut_repo = UserTrackRepository(self._session)
        sent = 0
        for user in users:
            local = now.astimezone(_tz(user.timezone))
            if local.weekday() != settings.digest_weekday:
                continue
            if not (settings.digest_window_start <= local.hour < settings.digest_window_end):
                continue
            iso = local.isocalendar()
            key = _SENT_KEY.format(user_id=user.id, week=f"{iso.year}-{iso.week}")
            if await self._redis.exists(key):
                continue
            ut = await ut_repo.get(user.id, _TRACK)
            if ut is None or (ut.settings or {}).get("push_blocked"):
                continue
            stats = await self._collect(user.id, (ut.settings or {}), user.streak_days, now)
            if stats.answers < _MIN_ANSWERS:
                # A quiet week — skip silently, don't recheck all evening.
                await self._redis.set(key, "1", ex=_SENT_TTL)
                continue
            try:
                await self._bot.send_message(
                    user.telegram_id, format_digest(stats), parse_mode="HTML"
                )
            except Exception:  # noqa: BLE001 — blocked / deactivated; next week is fine
                log.warning("digest_send_failed", uid=user.id)
                await self._redis.set(key, "1", ex=_SENT_TTL)
                continue
            await self._redis.set(key, "1", ex=_SENT_TTL)
            # Snapshot mastered count so next week's digest can show the delta.
            await UserTrackService(ut_repo).update_settings(
                user.id, _TRACK, {"digest_mastered": stats.mastered_total}
            )
            sent += 1
        return sent

    async def _collect(
        self, user_id: int, ut_settings: dict, streak_days: int, now: datetime
    ) -> WeekStats:
        since = now - timedelta(days=7)
        words_correct, words_wrong = await self._result_counts(WordReview, user_id, since)
        grammar_correct, grammar_wrong = await self._result_counts(GrammarReview, user_id, since)
        mastered_total = await UserWordRepository(self._session).count_status(
            user_id, _TRACK, WordStatus.MASTERED
        )
        prev = ut_settings.get("digest_mastered")
        delta = mastered_total - int(prev) if isinstance(prev, int) else None
        return WeekStats(
            words_correct=words_correct,
            words_wrong=words_wrong,
            grammar_correct=grammar_correct,
            grammar_wrong=grammar_wrong,
            mastered_total=mastered_total,
            mastered_delta=delta,
            streak_days=streak_days,
            hardest=await self._hardest_word(user_id, since),
        )

    async def _result_counts(self, model, user_id: int, since: datetime) -> tuple[int, int]:
        """(correct-ish, wrong-ish) review counts for the window."""
        q = (
            select(model.result, func.count())
            .where(
                model.user_id == user_id,
                model.track == _TRACK.value,
                model.reviewed_at >= since,
            )
            .group_by(model.result)
        )
        correct = wrong = 0
        for result, n in (await self._session.execute(q)).all():
            if result in (
                ReviewResult.CORRECT.value,
                ReviewResult.NORMAL.value,
                ReviewResult.EASY.value,
            ):
                correct += n
            else:
                wrong += n
        return correct, wrong

    async def _hardest_word(self, user_id: int, since: datetime) -> tuple[str, int] | None:
        q = (
            select(Word.writing, func.count().label("wrongs"))
            .join(UserWord, UserWord.word_id == Word.id)
            .join(WordReview, WordReview.user_word_id == UserWord.id)
            .where(
                WordReview.user_id == user_id,
                WordReview.track == _TRACK.value,
                WordReview.reviewed_at >= since,
                WordReview.result == ReviewResult.WRONG.value,
            )
            .group_by(Word.writing)
            .having(func.count() >= _HARDEST_MIN_WRONG)
            .order_by(func.count().desc())
            .limit(1)
        )
        row = (await self._session.execute(q)).first()
        return (row[0], row[1]) if row is not None else None
