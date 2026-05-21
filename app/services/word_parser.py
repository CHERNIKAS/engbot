from __future__ import annotations

import re
from dataclasses import dataclass

# Single tolerant parser for both manual input and TXT files.
#
# Supported per-line formats:
#   word
#   word - translation         (also: — or =)
#   word | example
#   word - translation | example
#
# - Trims whitespace, strips BOM, skips blank lines and `#` comments.
# - Deduplicates within the same input by normalized word (lowercase + nfkc-ish).

_BOM = "﻿"
_TRANSLATION_SEPS = re.compile(r"\s*[-—=–]\s*", re.UNICODE)
_VALID_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-'\s]{0,63}$")


@dataclass(frozen=True)
class ParsedWord:
    english: str
    normalized: str
    translation: str | None
    example: str | None


@dataclass
class ParseResult:
    words: list[ParsedWord]
    seen_count: int      # all non-blank lines that parsed to something (incl. invalid + duplicates)
    duplicates: int      # how many were dedup'd within this input
    invalid: int         # how many failed validation


def normalize(word: str) -> str:
    return word.strip().lower()


def _split_line(line: str) -> tuple[str, str | None, str | None]:
    # First split on " | " for example.
    example: str | None = None
    if "|" in line:
        word_part, _, example_part = line.partition("|")
        line = word_part.strip()
        example = example_part.strip() or None

    # Then split on separator for translation.
    parts = _TRANSLATION_SEPS.split(line, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip() or None, example
    return line.strip(), None, example


def _valid_english(word: str) -> bool:
    if not word:
        return False
    return bool(_VALID_WORD_RE.match(word))


def parse_input(
    text: str,
    *,
    max_lines: int = 5000,
    max_words: int = 1000,
) -> ParseResult:
    if not text:
        return ParseResult(words=[], seen_count=0, duplicates=0, invalid=0)

    text = text.lstrip(_BOM)
    # Tolerate any line ending.
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    seen_count = 0
    invalid = 0
    duplicates = 0
    seen_norm: set[str] = set()
    out: list[ParsedWord] = []

    for idx, raw in enumerate(raw_lines):
        if idx >= max_lines:
            break
        line = raw.strip().lstrip(_BOM)
        if not line or line.startswith("#"):
            continue

        seen_count += 1
        english, translation, example = _split_line(line)
        if not _valid_english(english):
            invalid += 1
            continue

        norm = normalize(english)
        if norm in seen_norm:
            duplicates += 1
            continue
        seen_norm.add(norm)
        out.append(
            ParsedWord(
                english=english.strip(),
                normalized=norm,
                translation=translation,
                example=example,
            )
        )
        if len(out) >= max_words:
            break

    return ParseResult(words=out, seen_count=seen_count, duplicates=duplicates, invalid=invalid)
