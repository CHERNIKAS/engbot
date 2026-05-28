from __future__ import annotations

import html
import json
import random
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.push import (
    SNOOZE_LABELS,
    push_card_kb,
    push_grammar_card_kb,
    push_rule_kb,
)
from app.bot.texts import (
    PUSH_ANSWER_CORRECT,
    PUSH_ANSWER_WRONG,
    PUSH_CARD,
    PUSH_GRAMMAR_CARD,
    PUSH_HIDDEN,
    PUSH_KNOWN,
    PUSH_RULE_CARD,
    PUSH_SNOOZED,
    PUSH_STALE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult, WordStatus
from app.domain.models import User, UserTrack
from app.domain.push import in_window, normalize_window
from app.domain.push_nudges import nudge_line
from app.infrastructure.repositories.grammar import GrammarRepository
from app.infrastructure.repositories.reviews import GrammarReviewRepository, WordReviewRepository
from app.infrastructure.repositories.user_words import UserWordRepository
from app.logging_setup import get_logger
from app.services.progress_service import ProgressService
from app.services.repetition_service import apply_review

log = get_logger("push")

_KEY = "push:{user_id}"
_TTL = 172_800  # 2 days
_TRACK = LearningTrack.ENGLISH


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _minutes(a: int, b: int) -> float:
    return random.randint(a, b) * 60.0


def _progress_line(uw) -> str:
    """Small progress hint shown under the word on a push card."""
    if uw.status == WordStatus.MASTERED.value:
        return f"⭐ {uw.mastery_score:.1f} / 5"
    return f"🌱 {uw.repetitions_count} / 10"


# Post-answer recap blocks ----------------------------------------------------
#
# After the user taps a button the card text is replaced with feedback. We
# append a "recap" block — context the user couldn't see during the quiz
# (showing it earlier would have spoiled the answer):
#   • for a word card:   writing — translation + example with the word bolded
#   • for a grammar card: the prompt with the gap filled in and the answer bold
#
# Pure functions so the formatting is unit-testable.

def _highlight_target(sentence: str, target: str) -> str:
    """HTML-escape `sentence` and bold the first case-insensitive match of
    `target` inside it. Falls back to the plain escaped sentence when the target
    isn't there (e.g. example uses a conjugated form the heuristic misses)."""
    safe = html.escape(sentence)
    if not target:
        return safe
    safe_target = html.escape(target)
    pattern = re.compile(re.escape(safe_target), re.IGNORECASE)
    return pattern.sub(lambda m: f"<b>{m.group(0)}</b>", safe, count=1)


def _word_recap(word, correct_translation: str) -> str:
    """Post-answer block under a word card: `writing — translation` + example
    sentence with the target word bolded. Skips the example line if missing."""
    head = f"<b>{html.escape(word.writing)}</b> — {html.escape(correct_translation)}"
    if not word.example_sentence:
        return f"\n\n{head}"
    body = _highlight_target(word.example_sentence, word.writing)
    return f"\n\n{head}\n📝 <i>{body}</i>"


def _grammar_recap(prompt: str, correct: str) -> str:
    """Post-answer block under a grammar card: the prompt with the `___` gap
    filled in by the bolded correct form, so the user sees the full sentence."""
    safe_prompt = html.escape(prompt)
    bold_answer = f"<b>{html.escape(correct)}</b>"
    filled = safe_prompt.replace("___", bold_answer, 1)
    return f"\n\n📝 <i>{filled}</i>"


class PushService:
    def __init__(self, session: AsyncSession, redis: Redis, bot: Bot | None = None) -> None:
        self._session = session
        self._redis = redis
        self._bot = bot
        self._uw = UserWordRepository(session)
        self._grammar = GrammarRepository(session)
        self._reviews = WordReviewRepository(session)
        self._grammar_reviews = GrammarReviewRepository(session)
        self._s = get_settings()

    # ---- state ----

    async def _load(self, user_id: int) -> dict:
        raw = await self._redis.get(_KEY.format(user_id=user_id))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    async def _save(self, user_id: int, state: dict) -> None:
        await self._redis.set(_KEY.format(user_id=user_id), json.dumps(state, ensure_ascii=False), ex=_TTL)

    def _window(self, ut: UserTrack) -> tuple[int, int]:
        s = ut.settings or {}
        return normalize_window(
            int(s.get("push_ws", self._s.push_default_window_start)),
            int(s.get("push_we", self._s.push_default_window_end)),
            min_hours=self._s.push_min_window_hours,
            default=(self._s.push_default_window_start, self._s.push_default_window_end),
        )

    # ---- worker tick ----

    async def run_all(self) -> int:
        # Push-learning is the main mode — on for every onboarded user.
        from app.infrastructure.repositories.user_tracks import UserTrackRepository
        from app.infrastructure.repositories.users import UserRepository

        if self._bot is None:
            return 0
        ut_repo = UserTrackRepository(self._session)
        pushed = 0
        for user in await UserRepository(self._session).list_for_push():
            ut = await ut_repo.get(user.id, _TRACK)
            if ut is None:
                continue
            # Commit per user: a tick can write (e.g. marking a grammar rule
            # seen), so one user's failure must not poison the shared transaction.
            try:
                if await self.run_tick(user, ut):
                    pushed += 1
                await self._session.commit()
            except Exception:  # noqa: BLE001
                await self._session.rollback()
                log.warning("push_tick_failed", uid=user.id)
        return pushed

    async def run_tick(self, user: User, ut: UserTrack) -> bool:
        ws, we = self._window(ut)
        now = datetime.now(timezone.utc)
        local = now.astimezone(_tz(user.timezone))
        now_ts = now.timestamp()
        today = local.date().isoformat()

        state = await self._load(user.id)
        if state.get("day") != today:
            # Yesterday's card (+ any rule message) stays in chat with live
            # buttons after the day rolls over — tidy it so the user doesn't tap
            # a ghost card the next morning and get a stale-callback.
            prev = state.get("inflight") or {}
            for k in ("msg_id", "rule_msg_id"):
                mid = prev.get(k)
                if mid:
                    await self._delete(user.telegram_id, int(mid))
            state = {"day": today, "next_ts": 0.0, "inflight": None}

        win = in_window(local.hour, ws, we)
        inflight = state.get("inflight")

        # ---- a card is waiting for an answer: keep nudging the SAME card until
        #      the user replies (the "force"); replace the old message each time.
        #      Each re-push carries an escalating "stop ignoring me" line.
        if inflight is not None:
            sent = False
            if win and now_ts >= inflight.get("retry_ts", 0):
                attempts = int(inflight.get("attempts", 0)) + 1
                inflight["attempts"] = attempts
                new_msg_id, _o, _c = await self._send_card(
                    user,
                    inflight.get("kind", "word"),
                    int(inflight.get("id", inflight.get("uw_id", 0))),
                    options_override=inflight.get("options"),
                    prefix=nudge_line(attempts),
                )
                if new_msg_id:
                    old_msg_id = inflight.get("msg_id")
                    if old_msg_id:
                        await self._delete(user.telegram_id, old_msg_id)
                    inflight["msg_id"] = new_msg_id
                    inflight["retry_ts"] = now_ts + _minutes(
                        self._s.push_retry_min_minutes, self._s.push_retry_max_minutes
                    )
                    sent = True
            await self._save(user.id, state)
            return sent

        # ---- no card pending: gated by the window + the post-answer gap ----
        if not win or now_ts < state.get("next_ts", 0.0):
            await self._save(user.id, state)
            return False

        # ---- a grammar rule waiting to be introduced? show it once, first ----
        rule_topic = await self._grammar.pending_rule(user.id, _TRACK)
        if rule_topic is not None:
            msg_id = await self._raw_send(
                user.telegram_id,
                PUSH_RULE_CARD.format(title=html.escape(rule_topic.title), rule=rule_topic.rule),
                push_rule_kb(),
            )
            if msg_id:
                await self._grammar.mark_rule_seen(user.id, rule_topic.id)
                state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
            await self._save(user.id, state)
            return msg_id is not None

        # ---- pick the next card: random among streams (words + grammar) ----
        #   "new" — introduce a new word (only if the active set has room)
        #   "repeat" — reinforce a random word being learned
        #   "review" — a mastered word due for review
        #   "grammar" — a non-mastered grammar exercise
        # Don't serve the same card twice in a row — skip whatever was answered
        # last (a small active set + ORDER BY random() otherwise repeats a word).
        last = state.get("last") or {}
        last_word = int(last.get("id", 0)) if last.get("kind") == "word" else 0
        last_grammar = int(last.get("id", 0)) if last.get("kind") == "grammar" else 0

        active_count = await self._uw.count_active(user.id, _TRACK)
        streams: list[str] = ["repeat", "review"]
        if active_count < ut.daily_goal_words:
            streams.append("new")
        grammar_pick = await self._grammar.pick_for_push(user.id, _TRACK, exclude_id=last_grammar)
        if grammar_pick is not None:
            streams.append("grammar")
        random.shuffle(streams)

        sent = False
        for stream in streams:
            if stream == "grammar":
                ugi, _gi = grammar_pick
                msg_id, options, correct = await self._send_card(user, "grammar", ugi.id)
                if msg_id:
                    state["inflight"] = self._inflight("grammar", ugi.id, options, correct, now_ts, msg_id)
                    sent = True
                break
            if stream == "new":
                pick = await self._uw.pick_new_for_push(user.id, _TRACK)
            elif stream == "repeat":
                pick = await self._uw.pick_active_random(user.id, _TRACK, exclude_uw_id=last_word)
            else:
                pick = await self._uw.pick_review_mastered(user.id, _TRACK, exclude_uw_id=last_word)
            if pick is None:
                continue
            uw, _w = pick
            msg_id, options, correct = await self._send_card(user, "word", uw.id)
            if msg_id:
                state["inflight"] = self._inflight("word", uw.id, options, correct, now_ts, msg_id)
                sent = True
            break

        await self._save(user.id, state)
        return sent

    def _inflight(
        self, kind: str, item_id: int, options: list[str], correct: str, now_ts: float, msg_id: int | None = None
    ) -> dict:
        return {
            "kind": kind,
            "id": item_id,
            "uw_id": item_id,  # back-compat for the answer callback validation
            "options": options,
            "correct": correct,
            "msg_id": msg_id,
            "attempts": 0,
            "retry_ts": now_ts + _minutes(self._s.push_retry_min_minutes, self._s.push_retry_max_minutes),
        }

    async def _send_card(
        self, user: User, kind: str, item_id: int, options_override: list[str] | None = None, prefix: str = ""
    ) -> tuple[int | None, list[str] | None, str | None]:
        """Build and send a card (word or grammar). Returns (msg_id, options,
        correct). On a re-push pass options_override so the button order matches
        the stored inflight (otherwise a re-shuffle would break answer checking)."""
        built = await self._build_grammar(item_id) if kind == "grammar" else await self._build_card(user.id, item_id)
        if built is None:
            return None, None, None
        text = built[0]
        options = options_override or built[1]
        correct = built[2]
        if prefix:
            text = f"{prefix}\n\n{text}"
        if kind == "grammar":
            kb = push_grammar_card_kb(options, item_id)
        else:
            kb = push_card_kb(options, item_id, built[3])
        msg_id = await self._raw_send(user.telegram_id, text, kb)
        return msg_id, options, correct

    async def _raw_send(self, telegram_id: int, text: str, reply_markup) -> int | None:
        """Send a push card with a prebuilt keyboard; return the new message_id
        (so retries can delete the previous one), or None on failure."""
        if self._bot is None:
            return None
        try:
            msg = await self._bot.send_message(
                telegram_id, text, reply_markup=reply_markup, parse_mode="HTML"
            )
            return msg.message_id
        except Exception:  # noqa: BLE001 — user may have blocked the bot
            log.warning("push_send_failed", tg=telegram_id)
            return None

    async def _build_grammar(self, ugi_id: int) -> tuple[str, list[str], str] | None:
        pair = await self._grammar.item_with_progress(ugi_id)
        if pair is None:
            return None
        ugi, item = pair
        options = [item.correct, *(item.distractors or [])][:4]
        random.shuffle(options)
        text = f"{PUSH_GRAMMAR_CARD.format(prompt=html.escape(item.prompt))}\n<i>{_progress_line(ugi)}</i>"
        return text, options, item.correct

    async def _delete(self, chat_id: int, message_id: int) -> None:
        """Drop a stale push message from chat. If Telegram refuses (too old to
        delete — >48h), at least strip the buttons so the user can't tap a ghost
        card and trigger a stale-callback."""
        if self._bot is None:
            return
        try:
            await self._bot.delete_message(chat_id, message_id)
            return
        except Exception:  # noqa: BLE001 — message may already be gone / too old
            pass
        try:
            await self._bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=None
            )
        except Exception:  # noqa: BLE001 — already stripped / gone
            pass

    async def _build_card(
        self, user_id: int, uw_id: int
    ) -> tuple[str, list[str], str, str] | None:
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return None
        uw, word = pair
        correct = uw.custom_translation or word.translation
        if not correct:
            return None
        distractors = await self._uw.quiz_distractors(
            user_id, track=_TRACK, exclude_user_word_id=uw_id, limit=3, exclude_translations=[correct],
            correct_pos=word.part_of_speech, correct_level=word.level,
        )
        options = [correct, *distractors[:3]]
        random.shuffle(options)
        text = f"{PUSH_CARD.format(word=html.escape(word.writing))}\n<i>{_progress_line(uw)}</i>"
        return text, options, correct, uw.status

    async def show_rule(self, user: User, ugi_id: int, query: CallbackQuery) -> None:
        """Show the rule behind a grammar exercise (the "📖 Правило" button), as a
        separate message tied to the current card so it's cleaned up on answer.
        Sends via the callback's message (handler path has no self._bot)."""
        if query.message is None:
            await query.answer()
            return
        state = await self._load(user.id)
        inflight = state.get("inflight")
        # Stale rule tap: the card is no longer the active inflight (day rolled
        # over, or the user is fishing in old cards). Clean it up instead of
        # opening a rule message for nothing.
        if not inflight or int(inflight.get("id", 0)) != ugi_id or inflight.get("kind") != "grammar":
            try:
                await query.message.delete()
            except Exception:  # noqa: BLE001 — too old / already gone
                try:
                    await query.message.edit_reply_markup(reply_markup=None)
                except Exception:  # noqa: BLE001
                    pass
            await query.answer()
            return
        topic = await self._grammar.topic_for_user_item(ugi_id)
        if topic is None:
            await query.answer()
            return
        bot, chat_id = query.message.bot, query.message.chat.id
        # Don't stack rule messages — drop a previously-opened one first.
        if inflight and inflight.get("rule_msg_id"):
            try:
                await bot.delete_message(chat_id, int(inflight["rule_msg_id"]))
            except Exception:  # noqa: BLE001
                pass
            inflight["rule_msg_id"] = None
        try:
            sent = await query.message.answer(
                PUSH_RULE_CARD.format(title=html.escape(topic.title), rule=topic.rule),
                reply_markup=push_rule_kb(),
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            sent = None
        if sent is not None and inflight is not None:
            inflight["rule_msg_id"] = sent.message_id
            await self._save(user.id, state)
        await query.answer()

    # ---- card controls (handler path): я знаю / перестать показывать / отложить ----

    async def handle_remove(self, user: User, uw_id: int, query: CallbackQuery, *, known: bool) -> None:
        uw = await self._uw.get(uw_id)
        if uw is not None:
            uw.archived = True
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_KNOWN if known else PUSH_HIDDEN)

    async def handle_snooze(self, user: User, uw_id: int, days: int, query: CallbackQuery) -> None:
        uw = await self._uw.get(uw_id)
        if uw is not None:
            uw.snooze_until = datetime.now(timezone.utc) + timedelta(days=days)
            await self._session.flush()
        await self._advance_after_card(user.id, uw_id)
        await self._finish_card(query, PUSH_SNOOZED.format(label=SNOOZE_LABELS.get(days, f"{days} дн.")))

    async def _advance_after_card(self, user_id: int, uw_id: int) -> None:
        """Drop the current card and let the next one come on the next worker tick."""
        state = await self._load(user_id)
        inflight = state.get("inflight")
        if inflight and int(inflight.get("uw_id", 0)) == uw_id:
            state["inflight"] = None
        state["next_ts"] = datetime.now(timezone.utc).timestamp()
        await self._save(user_id, state)

    async def _finish_card(self, query: CallbackQuery, text: str) -> None:
        if query.message:
            try:
                await query.message.edit_text(text)
            except Exception:  # noqa: BLE001
                pass
        await query.answer(text)

    # ---- answer (handler path) ----

    async def handle_answer(
        self, user: User, ut: UserTrack, uw_id: int, idx: int, query: CallbackQuery
    ) -> None:
        state = await self._load(user.id)
        inflight = state.get("inflight")
        iid = int(inflight.get("id", inflight.get("uw_id", 0))) if inflight else 0
        if not inflight or iid != uw_id:
            # Tapped on an old card whose inflight is gone. Don't just toast —
            # remove the ghost from chat so it stops accumulating.
            if query.message is not None:
                try:
                    await query.message.delete()
                except Exception:  # noqa: BLE001 — too old / already gone
                    try:
                        await query.message.edit_reply_markup(reply_markup=None)
                    except Exception:  # noqa: BLE001
                        pass
            await query.answer(PUSH_STALE, show_alert=False)
            return
        options = inflight.get("options") or []
        if idx < 0 or idx >= len(options):
            await query.answer()
            return
        correct = options[idx] == inflight.get("correct")
        correct_answer_text = str(inflight.get("correct") or "")
        rule_msg_id = inflight.get("rule_msg_id")

        # Build the post-answer recap block (example for words, filled prompt for
        # grammar) — fetched here, used after we save state.
        recap = ""
        if inflight.get("kind") == "grammar":
            await self._apply_grammar_answer(user, ut, iid, correct)
            pair = await self._grammar.item_with_progress(iid)
            if pair is not None:
                _ugi, item = pair
                recap = _grammar_recap(item.prompt, item.correct)
        else:
            await self._apply_word_answer(user, ut, iid, correct)
            pair = await self._uw.get_with_word(iid)
            if pair is not None:
                _uw, word = pair
                recap = _word_recap(word, correct_answer_text)

        now_ts = datetime.now(timezone.utc).timestamp()
        state["inflight"] = None
        # Remember this card so the next pick skips it (no back-to-back repeats).
        state["last"] = {"kind": inflight.get("kind", "word"), "id": iid}
        state["next_ts"] = now_ts + _minutes(self._s.push_gap_min_minutes, self._s.push_gap_max_minutes)
        await self._save(user.id, state)

        # Clean up the rule message the user may have opened for this card
        # (handler path has no self._bot, so use the callback's message bot).
        if rule_msg_id and query.message is not None:
            try:
                await query.message.bot.delete_message(query.message.chat.id, int(rule_msg_id))
            except Exception:  # noqa: BLE001
                pass

        feedback = (
            PUSH_ANSWER_CORRECT
            if correct
            else PUSH_ANSWER_WRONG.format(answer=html.escape(correct_answer_text))
        ) + recap
        if query.message:
            try:
                await query.message.edit_text(feedback, parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        await query.answer("✅" if correct else "❌")

    async def _apply_word_answer(self, user: User, ut: UserTrack, uw_id: int, correct: bool) -> None:
        uw = await self._uw.get(uw_id)
        if uw is None:
            return
        was_mastered = uw.status == WordStatus.MASTERED.value
        apply_review(uw, ReviewResult.CORRECT if correct else ReviewResult.WRONG, LearningPace(ut.learning_pace))
        await self._reviews.create(
            user_id=user.id, track=_TRACK, user_word_id=uw_id,
            session_id=None, result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
        )
        await self._session.flush()
        await ProgressService(self._session).update_streak(user)
        # A word just got mastered → a course slot freed up; top the pipeline back up.
        if not was_mastered and uw.status == WordStatus.MASTERED.value:
            from app.services.course_service import CourseService

            await CourseService(self._session, self._redis).refill(user, ut, _TRACK)

    async def _apply_grammar_answer(self, user: User, ut: UserTrack, ugi_id: int, correct: bool) -> None:
        ugi = await self._grammar.get_user_item(ugi_id)
        if ugi is None:
            return
        was_mastered = ugi.status == WordStatus.MASTERED.value
        apply_review(ugi, ReviewResult.CORRECT if correct else ReviewResult.WRONG, LearningPace(ut.learning_pace))
        await self._grammar_reviews.create(
            user_id=user.id, track=_TRACK, user_grammar_item_id=ugi_id,
            result=(ReviewResult.CORRECT if correct else ReviewResult.WRONG).value,
        )
        await self._session.flush()
        await ProgressService(self._session).update_streak(user)
        # Grammar item mastered → advance the course (next topic + word top-up).
        if not was_mastered and ugi.status == WordStatus.MASTERED.value:
            from app.services.course_service import CourseService

            await CourseService(self._session, self._redis).refill(user, ut, _TRACK)
