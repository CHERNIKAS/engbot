"""Keeps `words.level` / `words.freq_rank` filled in as new words arrive.

Migration 0037 tagged the 1116 words that had no level, but every word a user
adds afterwards — quick-add, TXT import — lands untagged, and an untagged word
is invisible to level-based selection. Without this the gap simply grows back.

Runs as a background worker, never on the request path: tagging is not urgent
(an untagged word is treated as at-level until its turn comes), and no user
should wait on a third-party API to finish adding a word.

Disabled cleanly when GEMINI_API_KEY is unset — the bot then behaves exactly as
it did before, with new words staying untagged.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.enums import LearningTrack
from app.domain.levels import LEVELS
from app.domain.models import Word
from app.logging_setup import get_logger

log = get_logger("level_tagger")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Shared with scripts/level_words.py so the one-off backfill and the ongoing
# worker grade on the same scale — a drifting prompt would quietly split the
# catalogue into two differently-calibrated halves.
SYSTEM_PROMPT = """Ты лексикограф. Для каждого английского слова определи:

1. level — уровень CEFR (A1, A2, B1, B2, C1, C2), на котором это слово обычно
   вводят изучающим английский как иностранный.
   A1 — базовые бытовые слова (cat, go, big).
   A2 — расширенный быт (weather, decide, careful).
   B1 — обиходно-абстрактное (achieve, opinion, reliable).
   B2 — более книжное и точное (reluctant, thorough, allocate).
   C1/C2 — редкое, узкоспециальное, книжное (ubiquitous, unwieldy).

2. freq — насколько часто слово встречается в обычном английском:
   1 = очень частое (входит в первую тысячу),
   2 = частое, 3 = среднее, 4 = редкое, 5 = очень редкое / узкий термин.

Термин из узкой области (крипта, медицина, юриспруденция) получает уровень по
своей лексической сложности, а freq — 4 или 5.

КАЛИБРОВКА. Ниже — эталонная шкала этого курса. Ориентируйся на неё, а не на
собственное представление о сложности: шкала курса заметно мягче типичных
учебных списков.

A1: loud, worry, place, work, try, market, neighbour, word, ready, enter
A2: daily, wipe, piece, mix, safe, rescue, whisper, breathe, list, fix
B1: certain, aware, perfect, settle, relate, alone, purpose, honest, legal, replace
B2: stability, variable, condemn, subsequent, abstract, phase, ambition, ambiguous, adequate, constraint

Замечено, что модели завышают уровень примерно на один шаг. Если колеблешься
между двумя соседними уровнями — выбирай МЛАДШИЙ.

Отвечай строго JSON-массивом того же размера и в том же порядке, что и вход."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "level": {"type": "STRING", "enum": list(LEVELS)},
            "freq": {"type": "INTEGER"},
        },
        "required": ["id", "level", "freq"],
    },
}

# The free tier answers 503 "high demand" now and then. One retry clears it; a
# longer chain isn't worth it when the next worker tick is minutes away anyway.
_RETRIES = 2
_RETRY_PAUSE = 3.0


class LevelTaggerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self._settings.gemini_api_key)

    async def run(self, track: LearningTrack = LearningTrack.ENGLISH) -> int:
        """Tag one batch of untagged words. Returns how many were written."""
        if not self.enabled:
            return 0
        rows = await self._untagged(track, self._settings.level_tagger_batch)
        if not rows:
            return 0
        try:
            tagged = await self._ask(rows)
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            # Nothing is lost: these words stay untagged and are retried on the
            # next tick, so a flaky API never blocks or corrupts anything.
            log.warning("level_tagger_call_failed", error=type(exc).__name__, batch=len(rows))
            return 0
        return await self._write(tagged)

    async def _untagged(self, track: LearningTrack, limit: int) -> list[Word]:
        q = (
            select(Word)
            .where(
                Word.track == track.value,
                Word.level.is_(None),
                Word.translation.isnot(None),
            )
            .order_by(Word.id.asc())
            .limit(limit)
        )
        return list((await self._session.execute(q)).scalars().all())

    async def _ask(self, words: list[Word]) -> dict[int, tuple[str, int]]:
        listing = "\n".join(f"{w.id}. {w.writing} — {w.translation}" for w in words)
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": listing}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                "temperature": 0,
            },
        }
        url = API_URL.format(model=self._settings.ai_model)
        timeout = aiohttp.ClientTimeout(total=self._settings.ai_timeout_seconds)
        last: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as http:
                    async with http.post(
                        url, params={"key": self._settings.gemini_api_key}, json=payload
                    ) as resp:
                        if resp.status in (429, 500, 503):
                            raise aiohttp.ClientError(f"HTTP {resp.status}")
                        resp.raise_for_status()
                        data = await resp.json()
                return self._parse(data)
            except (TimeoutError, aiohttp.ClientError) as exc:
                last = exc
                if attempt + 1 < _RETRIES:
                    await asyncio.sleep(_RETRY_PAUSE)
        raise last if last else ValueError("no response")

    @staticmethod
    def _parse(data: dict[str, Any]) -> dict[int, tuple[str, int]]:
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            rows = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("unparseable response") from exc
        out: dict[int, tuple[str, int]] = {}
        for row in rows if isinstance(rows, list) else []:
            level = row.get("level")
            if level not in LEVELS:
                continue  # a level outside the scale is a model slip, not data
            try:
                word_id = int(row["id"])
                freq = int(row.get("freq", 3))
            except (KeyError, TypeError, ValueError):
                continue
            out[word_id] = (level, max(1, min(5, freq)))
        return out

    async def _write(self, tagged: dict[int, tuple[str, int]]) -> int:
        written = 0
        for word_id, (level, freq) in tagged.items():
            # `level IS NULL` in the WHERE clause: a word tagged by someone else
            # (or by a migration) between the read and the write keeps its value.
            result = await self._session.execute(
                update(Word)
                .where(Word.id == word_id, Word.level.is_(None))
                .values(level=level, freq_rank=freq)
            )
            written += result.rowcount or 0
        await self._session.flush()
        if written:
            log.info("words_tagged", count=written)
        return written
