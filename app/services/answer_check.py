"""Understands what the learner actually wrote, when it isn't an exact match.

The strict check answers one question — do the strings match. That treats four
very different situations identically:

    relaible     a slip on a long word; they know it
    receive      a valid synonym; they know it, just not this word
    I am agree   the right word in the wrong form
    forget       they don't know it

All four scored "❌ Мимо" and cost the same. This classifies them, and
`app/domain/mastery.py` — not the model — decides what each classification is
worth. A model slip can misprice one answer by a fraction of a point; it cannot
hand anyone a mastered word.

Only ever consulted when the strict check has already failed, so a correct
answer is still instant and free. When the API is unreachable the caller falls
back to the strict verdict and the card says so, rather than the bot silently
becoming stricter than the day before.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp
from redis.asyncio import Redis

from app.config import get_settings
from app.domain import mastery
from app.logging_setup import get_logger

log = get_logger("answer_check")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Verdicts the model may return, mapped to what the score table calls them.
VERDICT_TO_KIND = {
    "typo": mastery.TYPED_TYPO,
    "synonym": mastery.TYPED_SYNONYM,
    "grammar": mastery.TYPED_GRAMMAR,
    "wrong": mastery.WRONG,
}

SYSTEM_PROMPT = """Ты проверяешь ответ ученика в тренажёре английских слов.

Дано: правильное английское слово, его перевод и то, что написал ученик.
Определи, что произошло:

- "typo" — то же слово с опечаткой или мелкой ошибкой написания (relaible → reliable).
- "synonym" — другое английское слово, но по смыслу подходящее к переводу
  (receive вместо obtain).
- "grammar" — нужное слово есть, но в неверной форме или окружении
  (I am agree вместо I agree; goed вместо went).
- "wrong" — другое по смыслу слово, или бессмыслица.

ЖЕЛЕЗНОЕ ПРАВИЛО: ответ должен быть НА АНГЛИЙСКОМ. Если ученик написал
кириллицей — это всегда "wrong", даже если он написал верный перевод.
Задание — вспомнить английское слово, а не перевести обратно.

hint — объяснение того, ЧТО именно не так. Максимум 12 слов, без воды и похвалы.

hint ПИШЕТСЯ ТОЛЬКО ПО-РУССКИ. Целиком, каждое слово. Английской может быть
только сама разбираемая словоформа. Человек читает эту подсказку именно потому,
что не справился с английским, — объяснение на английском ему бесполезно.

Отвечай строго JSON."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "verdict": {"type": "STRING", "enum": list(VERDICT_TO_KIND)},
        "hint": {"type": "STRING"},
    },
    "required": ["verdict", "hint"],
}

# Wrong answers repeat — the same misspelling comes back from the same person
# and from different ones. A month is long enough to make that pay and short
# enough that a prompt change works through.
_CACHE_KEY = "ansck:{word}:{answer}"
_CACHE_TTL = 2_592_000
_MAX_ANSWER_LEN = 64


@dataclass(frozen=True)
class AnswerVerdict:
    kind: str  # an app.domain.mastery answer kind
    hint: str

    @property
    def credited(self) -> bool:
        """Whether this counts as knowing the word well enough to move on."""
        return self.kind in (mastery.TYPED_TYPO, mastery.TYPED_SYNONYM)


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


class AnswerCheckService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self._settings.gemini_api_key)

    async def classify(self, word: str, translation: str, answer: str) -> AnswerVerdict | None:
        """What kind of wrong answer this is, or None when we couldn't tell.

        None means "the API didn't answer" and is distinct from a "wrong"
        verdict: the caller shows the degraded-mode notice for one and a normal
        miss for the other.
        """
        answer = (answer or "").strip()[:_MAX_ANSWER_LEN]
        if not answer or not word:
            return AnswerVerdict(mastery.WRONG, "")
        if _has_cyrillic(answer):
            # Settled here rather than by the model, which was observed marking
            # a Russian translation correct while its own hint said the answer
            # had to be in English.
            return AnswerVerdict(mastery.WRONG, "Нужно английское слово, не перевод.")
        if not self.enabled:
            return None

        cached = await self._cached(word, answer)
        if cached is not None:
            return cached
        try:
            verdict = await self._ask(word, translation, answer)
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            log.warning("answer_check_failed", error=type(exc).__name__)
            return None
        await self._remember(word, answer, verdict)
        return verdict

    def _key(self, word: str, answer: str) -> str:
        return _CACHE_KEY.format(word=word.lower(), answer=answer.lower())

    async def _cached(self, word: str, answer: str) -> AnswerVerdict | None:
        try:
            raw = await self._redis.get(self._key(word, answer))
        except Exception:  # noqa: BLE001 — a cache miss must never break an answer
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return AnswerVerdict(data["kind"], data.get("hint", ""))
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    async def _remember(self, word: str, answer: str, verdict: AnswerVerdict) -> None:
        try:
            await self._redis.set(
                self._key(word, answer),
                json.dumps({"kind": verdict.kind, "hint": verdict.hint}, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
        except Exception:  # noqa: BLE001 — caching is best-effort
            pass

    async def _ask(self, word: str, translation: str, answer: str) -> AnswerVerdict:
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Правильно: {word} | Перевод: {translation or '—'} "
                                f"| Ученик написал: {answer}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                "temperature": 0,
            },
        }
        timeout = aiohttp.ClientTimeout(total=self._settings.answer_check_timeout_seconds)
        url = API_URL.format(model=self._settings.ai_model)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.post(
                url, params={"key": self._settings.gemini_api_key}, json=payload
            ) as resp:
                if resp.status in (429, 500, 503):
                    raise aiohttp.ClientError(f"HTTP {resp.status}")
                resp.raise_for_status()
                data = await resp.json()
        return self._parse(data)

    @staticmethod
    def _parse(data: dict[str, Any]) -> AnswerVerdict:
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            row = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("unparseable response") from exc
        kind = VERDICT_TO_KIND.get(str(row.get("verdict")))
        if kind is None:
            # An unknown verdict is a model slip; the safe reading of a failed
            # strict check is that the answer was wrong.
            kind = mastery.WRONG
        hint = str(row.get("hint") or "").strip()
        return AnswerVerdict(kind, hint)


async def gather_with_timeout(coro, seconds: float):
    """Run `coro`, returning None if it outlives `seconds`. Keeps a slow API
    from holding up a card the user is waiting on."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except (TimeoutError, asyncio.CancelledError):
        return None
