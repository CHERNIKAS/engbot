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
    push_leech_kb,
    push_rule_kb,
)
from app.bot.texts import (
    PUSH_ANSWER_CORRECT,
    PUSH_ANSWER_WRONG,
    PUSH_CARD,
    PUSH_CARD_REVERSE,
    PUSH_GRAMMAR_CARD,
    PUSH_HIDDEN,
    PUSH_KNOWN,
    PUSH_LEECH_KEPT,
    PUSH_LEECH_PARKED,
    PUSH_LEECH_PROMPT,
    PUSH_RULE_CARD,
    PUSH_SNOOZED,
    PUSH_STALE,
)
from app.config import get_settings
from app.domain.enums import LearningPace, LearningTrack, ReviewResult, WordStatus
from app.domain.models import User, UserTrack
from app.domain.pacing import ceiling_of, pace_of
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

# Consecutive wrong answers before the bot offers to postpone a word (leech
# detection — one impossible word shouldn't clog a slot in the active pool).
LEECH_THRESHOLD = 6
LEECH_PARK_DAYS = 7

# Production ladder: a word climbs card types as it's answered correctly, so
# production is gated behind successful recognition (testing-effect boundary
# condition — retrieval must succeed for the benefit to stick). The "stage" is
# derived from repetitions_count (consecutive correct, reset to 0 on a miss) —
# no extra column needed; a miss naturally drops the word back to recognition.
#   reps 0-2 → recognition (EN→RU choice)
#   reps 3-5 → reverse     (RU→EN choice)
#   reps 6+  → cloze        (type the word into an English sentence)
STAGE_STEP = 3  # correct-in-a-row per rung
CARD_RECOGNITION = "recognition"
CARD_REVERSE = "reverse"
CARD_CLOZE = "cloze"


def _leech_after(consecutive_wrong_before: int, correct: bool, was_mastered: bool) -> tuple[int, bool]:
    """Update the consecutive-miss counter for a word and decide whether it just
    became a leech. Mastered words never become leeches (they ride a 0–5 score,
    not the active-learning track). Returns (new_counter, offer_to_postpone)."""
    if correct or was_mastered:
        return 0, False
    n = (consecutive_wrong_before or 0) + 1
    return n, n >= LEECH_THRESHOLD


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

_CLOZE_INFLECT = r"(?:s|es|ed|d|ing|ly|er|est)?"


def _mask_target(sentence: str, target: str) -> str | None:
    """Replace the target word (+ basic inflections) in `sentence` with ___ for a
    cloze card. Returns None when the word isn't found in a maskable form (e.g.
    an irregular like 'went' for 'go') — those words skip the cloze rung."""
    if not sentence or not target:
        return None
    pattern = re.compile(rf"\b{re.escape(target)}{_CLOZE_INFLECT}\b", re.IGNORECASE)
    masked, n = pattern.subn("___", sentence)
    return masked if n > 0 else None


def _format_word_card(writing: str, abstract_en: str | None, abstract_ru: str | None, progress: str) -> str:
    """Render the word push card. Includes a paired EN/RU abstract example
    underneath the question when both are present — these use synonyms /
    paraphrase so the target word isn't in the sentence (no spoilers). If
    either side is missing the example is skipped: better no hint than a
    half-baked one."""
    parts = [PUSH_CARD.format(word=html.escape(writing))]
    if abstract_en and abstract_ru:
        parts.append(f"📝 <i>{html.escape(abstract_en)}</i>")
        parts.append(f"<i>↳ {html.escape(abstract_ru)}</i>")
    parts.append(f"<i>{progress}</i>")
    return "\n".join(parts)


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
            state = {"day": today, "next_ts": 0.0, "inflight": None, "new_today": 0}

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
                    card_type=inflight.get("ctype", CARD_RECOGNITION),
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
        #   "new" — introduce a new word (gated by today's intake + pool ceiling)
        #   "repeat" — reinforce a random word being learned
        #   "review" — a mastered word due for review
        #   "grammar" — a non-mastered grammar exercise
        # Don't serve the same card twice in a row — skip whatever was answered
        # last (a small active set + ORDER BY random() otherwise repeats a word).
        last = state.get("last") or {}
        last_word = int(last.get("id", 0)) if last.get("kind") == "word" else 0
        last_grammar = int(last.get("id", 0)) if last.get("kind") == "grammar" else 0

        # New-word intake is decoupled from mastering old words: introduce up to
        # `pace` new words per day, but only while the active pool stays under
        # `ceiling` (pace × 3) — so growth is steady, not a flood that turns the
        # push into mush. (Old rule gated new on a word hitting 10-in-a-row.)
        pace = pace_of(ut.settings)
        ceiling = ceiling_of(pace)
        new_today = int(state.get("new_today", 0))
        active_count = await self._uw.count_active(user.id, _TRACK)

        streams: list[str] = ["repeat", "review"]
        if new_today < pace and active_count < ceiling:
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
            # Card type by production-ladder stage (recognition → reverse → cloze).
            ctype = self._card_type(uw, _w)
            msg_id, options, correct = await self._send_card(user, "word", uw.id, card_type=ctype)
            if msg_id:
                state["inflight"] = self._inflight("word", uw.id, options, correct, now_ts, msg_id, ctype=ctype)
                if stream == "new":
                    state["new_today"] = new_today + 1  # count an introduction
                sent = True
            break

        await self._save(user.id, state)
        return sent

    def _inflight(
        self,
        kind: str,
        item_id: int,
        options: list[str],
        correct: str,
        now_ts: float,
        msg_id: int | None = None,
        ctype: str = CARD_RECOGNITION,
    ) -> dict:
        return {
            "kind": kind,
            "id": item_id,
            "uw_id": item_id,  # back-compat for the answer callback validation
            "options": options,
            "correct": correct,
            "msg_id": msg_id,
            "ctype": ctype,
            "attempts": 0,
            "retry_ts": now_ts + _minutes(self._s.push_retry_min_minutes, self._s.push_retry_max_minutes),
        }

    async def _send_card(
        self,
        user: User,
        kind: str,
        item_id: int,
        options_override: list[str] | None = None,
        prefix: str = "",
        card_type: str = CARD_RECOGNITION,
    ) -> tuple[int | None, list[str] | None, str | None]:
        """Build and send a card (word or grammar). Returns (msg_id, options,
        correct). On a re-push pass options_override so the button order matches
        the stored inflight (otherwise a re-shuffle would break answer checking);
        `card_type` is likewise carried over so the prompt stays stable."""
        built = (
            await self._build_grammar(item_id)
            if kind == "grammar"
            else await self._build_card(user.id, item_id, card_type=card_type)
        )
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

    def _cloze_possible(self, word: Word) -> bool:
        """Cloze needs an example whose target word can be masked (regular form)."""
        return _mask_target(word.example_sentence or "", word.writing) is not None

    def _card_type(self, uw: UserWord, word: Word) -> str:
        """Which card type to show, by the word's production-ladder stage.
        New words always start on recognition; mastered words rotate types for
        review variety. Stage = consecutive-correct // STAGE_STEP."""
        if uw.status == WordStatus.NEW.value:
            return CARD_RECOGNITION
        if uw.status == WordStatus.MASTERED.value:
            choices = [CARD_RECOGNITION, CARD_REVERSE]
            if self._cloze_possible(word):
                choices.append(CARD_CLOZE)
            return random.choice(choices)
        stage = (uw.repetitions_count or 0) // STAGE_STEP
        if stage <= 0:
            return CARD_RECOGNITION
        if stage == 1:
            return CARD_REVERSE
        return CARD_CLOZE if self._cloze_possible(word) else CARD_REVERSE

    async def _build_card(
        self, user_id: int, uw_id: int, card_type: str = CARD_RECOGNITION
    ) -> tuple[str, list[str], str, str] | None:
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return None
        uw, word = pair
        ru = uw.custom_translation or word.translation
        if not ru:
            return None

        if card_type in (CARD_REVERSE, CARD_CLOZE):
            # RU prompt → pick the English word. Answer is the writing; distractors
            # are other English words. Closes the recognition→production gap.
            # (CARD_CLOZE renders as reverse until the typing rung lands.)
            distractors = await self._uw.reverse_distractors(
                user_id, track=_TRACK, exclude_word_id=word.id, limit=3,
                correct_pos=word.part_of_speech, correct_level=word.level,
            )
            answer = word.writing
            options = [answer, *distractors[:3]]
            random.shuffle(options)
            text = (
                f"{PUSH_CARD_REVERSE.format(translation=html.escape(ru))}"
                f"\n<i>{_progress_line(uw)}</i>"
            )
            return text, options, answer, uw.status

        # Recognition (default): EN→RU, pick the translation. Carries the abstract
        # example as a context hint.
        distractors = await self._uw.quiz_distractors(
            user_id, track=_TRACK, exclude_user_word_id=uw_id, limit=3, exclude_translations=[ru],
            correct_pos=word.part_of_speech, correct_level=word.level,
        )
        options = [ru, *distractors[:3]]
        random.shuffle(options)
        text = _format_word_card(
            writing=word.writing,
            abstract_en=word.abstract_example_en,
            abstract_ru=word.abstract_example_ru,
            progress=_progress_line(uw),
        )
        return text, options, ru, uw.status

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

        leech_writing: str | None = None
        if inflight.get("kind") == "grammar":
            await self._apply_grammar_answer(user, ut, iid, correct)
        else:
            leech_writing = await self._apply_word_answer(user, ut, iid, correct)

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
        )
        if query.message:
            try:
                await query.message.edit_text(feedback, parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        await query.answer("✅" if correct else "❌")

        # This word has been missed LEECH_THRESHOLD times in a row — offer to
        # postpone it so it stops blocking a slot. A separate message with its
        # own buttons (the card itself is already edited to feedback).
        if leech_writing and query.message is not None:
            try:
                await query.message.answer(
                    PUSH_LEECH_PROMPT.format(word=html.escape(leech_writing)),
                    reply_markup=push_leech_kb(iid),
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass

    async def handle_leech_park(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        """Postpone a stuck word: snooze it for LEECH_PARK_DAYS (out of rotation,
        frees its slot, auto-returns) and clear the miss streak."""
        uw = await self._uw.get(uw_id)
        if uw is not None and uw.user_id == user.id:
            uw.snooze_until = datetime.now(timezone.utc) + timedelta(days=LEECH_PARK_DAYS)
            uw.consecutive_wrong = 0
            await self._session.flush()
        await self._finish_card(query, PUSH_LEECH_PARKED)

    async def handle_leech_keep(self, user: User, uw_id: int, query: CallbackQuery) -> None:
        """Keep drilling a stuck word — just reset the miss streak so we don't
        nag again on the very next miss."""
        uw = await self._uw.get(uw_id)
        if uw is not None and uw.user_id == user.id:
            uw.consecutive_wrong = 0
            await self._session.flush()
        await self._finish_card(query, PUSH_LEECH_KEPT)

    async def _apply_word_answer(self, user: User, ut: UserTrack, uw_id: int, correct: bool) -> str | None:
        """Apply the SR result and leech tracking. Returns the word's writing
        when this wrong answer just crossed the leech threshold (so the caller
        can offer to postpone it), else None."""
        pair = await self._uw.get_with_word(uw_id)
        if pair is None:
            return None
        uw, word = pair
        was_mastered = uw.status == WordStatus.MASTERED.value
        apply_review(uw, ReviewResult.CORRECT if correct else ReviewResult.WRONG, LearningPace(ut.learning_pace))

        # Leech tracking: count consecutive misses on words still being learned.
        uw.consecutive_wrong, is_leech = _leech_after(uw.consecutive_wrong, correct, was_mastered)
        leech_writing = word.writing if is_leech else None

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
        return leech_writing

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
