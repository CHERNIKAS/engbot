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
# Tight delimiters (no surrounding spaces needed): ; tab — – =
# ASCII hyphen "-" is a separator ONLY when space-padded, so hyphenated words
# like "well-known" / "e-mail" are preserved.
_TRANSLATION_SEPS = re.compile(r"(?:\s*[;\t—–=]\s*)|(?:\s+-\s+)", re.UNICODE)
_QUOTE_CHARS = "\"'«»“”„"
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


def _strip_quotes(s: str) -> str:
    """Strip matching surrounding quotes (handles CSV-style `"word";"перевод"`)."""
    s = s.strip()
    while len(s) >= 2 and s[0] in _QUOTE_CHARS and s[-1] in _QUOTE_CHARS:
        s = s[1:-1].strip()
    return s


def _split_line(line: str) -> tuple[str, str | None, str | None]:
    # First split on "|" for example.
    example: str | None = None
    if "|" in line:
        word_part, _, example_part = line.partition("|")
        line = word_part.strip()
        example = _strip_quotes(example_part) or None

    # Then split on separator for translation (quotes stripped per field, so
    # `"which";"который"`, `hello\tпривет`, `word - перевод` all work).
    parts = _TRANSLATION_SEPS.split(line, maxsplit=1)
    if len(parts) == 2:
        return _strip_quotes(parts[0]), (_strip_quotes(parts[1]) or None), example
    return _strip_quotes(line), None, example


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
