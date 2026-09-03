from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import LearningTrack, WordSource
from app.infrastructure.example_provider.base import ExampleProvider
from app.infrastructure.repositories.user_words import UserWordRepository
from app.infrastructure.repositories.words import WordRepository
from app.services.word_parser import ParseResult, ParsedWord, parse_input


@dataclass
class ImportPreview:
    parse: ParseResult


@dataclass
class ImportResult:
    added: int
    skipped_existing: int
    # Catalogue ids touched by this import. Carried so the caller can offer
    # "teach these first" against exactly this batch and nothing older.
    word_ids: list[int] = field(default_factory=list)


class WordImportService:
    """Pipeline for manual + TXT imports. Track-aware: each word lands in the chosen track."""

    def __init__(
        self,
        word_repo: WordRepository,
        user_word_repo: UserWordRepository,
        example_provider: ExampleProvider,
    ) -> None:
        self._word_repo = word_repo
        self._user_word_repo = user_word_repo
        self._example_provider = example_provider

    @staticmethod
    def preview(text: str, *, max_lines: int, max_words: int) -> ImportPreview:
        return ImportPreview(parse=parse_input(text, max_lines=max_lines, max_words=max_words))

    async def commit(
        self,
        user_id: int,
        track: LearningTrack,
        words: list[ParsedWord],
        category_id: int | None,
        source: WordSource,
    ) -> ImportResult:
        if not words:
            return ImportResult(added=0, skipped_existing=0)

        rows: list[dict] = []
        for w in words:
            example = w.example
            # Only fetch local-DB examples for English; Japanese examples come from packs.
            if not example and track == LearningTrack.ENGLISH:
                example = await self._example_provider.get_example(w.normalized)
            rows.append(
                {
                    "writing": w.english,
                    "normalized_word": w.normalized,
                    "translation": w.translation,
                    "example_sentence": example,
                }
            )

        normalized_to_word = await self._word_repo.upsert_many(track, rows)

        for row in rows:
            existing = normalized_to_word.get(row["normalized_word"])
            if existing and not existing.example_sentence and row["example_sentence"]:
                await self._word_repo.update_example_if_empty(
                    existing.id, row["example_sentence"]
                )

        word_ids = [
            normalized_to_word[w.normalized].id
            for w in words
            if w.normalized in normalized_to_word
        ]
        added = await self._user_word_repo.bulk_add(
            user_id=user_id,
            track=track,
            word_ids=word_ids,
            category_id=category_id,
            source=source,
        )
        return ImportResult(
            added=added,
            skipped_existing=len(word_ids) - added,
            word_ids=word_ids,
        )
