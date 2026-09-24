"""Corpus frequency as the axis the word queue is ordered by.

Until now "how useful is this word" was a number from 1 to 5 that a language
model guessed per word. Measuring it against real corpus data showed what that
resolution costs: `salad`, `Friday` and `cheese` sat in the same bucket as
`you`, `not` and `the`. Five buckets cannot order two thousand words, so the
queue was effectively unordered inside each CEFR level — which is how a learner
at A1 ended up being taught `giggle` while 687 A1 words sat untouched.

The New General Service List gives a real rank instead: 2801 headwords from a
273-million-word corpus, covering ~92% of general English text. Rank 1 is `the`,
rank 36 is `would`. Lower is more useful, and the number means something all the
way down.

Two things this is NOT:

  * a difficulty order — the list is corpus-driven, so `whether` (273) outranks
    `apple`, which is absent entirely. Frequency says what a learner will meet,
    not what they can handle, which is why the CEFR level stays on as a ceiling
    and the thematic collections run alongside;
  * a teaching list — 69% of its first hundred entries are function words. See
    `app.domain.function_words`.

Attribution and licence: `app/infrastructure/data/NOTICE.md`.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "infrastructure" / "data"
_RANK_FILE = _DATA / "ngsl_rank.csv"
_FORMS_FILE = _DATA / "ngsl_forms.csv"

# Anything past the list is "rarer than the 2809th most common word". Sorting
# needs a finite value, and NULLS LAST in SQL covers the DB side; this is for
# the pure-Python callers.
UNRANKED = 10_000


@lru_cache(maxsize=1)
def _rank_map() -> dict[str, int]:
    out: dict[str, int] = {}
    with _RANK_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lemma = row["lemma"].strip().lower()
            if lemma:
                out[lemma] = int(row["rank"])
    return out


@lru_cache(maxsize=1)
def _form_map() -> dict[str, str]:
    out: dict[str, str] = {}
    with _FORMS_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            form = row["form"].strip().lower()
            head = row["headword"].strip().lower()
            if form and head:
                out[form] = head
    return out


def headword(writing: str | None) -> str | None:
    """The list entry this spelling belongs to, or None if it isn't on the list.

    Resolves inflections, which is what stops the catalogue counting `drove`,
    `driving` and `drive` as three separate things to learn.
    """
    if not writing:
        return None
    cleaned = writing.strip().lower()
    if not cleaned or " " in cleaned:
        return None
    if cleaned in _rank_map():
        return cleaned
    head = _form_map().get(cleaned)
    return head if head in _rank_map() else None


def rank_of(writing: str | None) -> int | None:
    """Corpus rank for this word (1 = most common), or None if it's off-list.

    None is meaningful: it marks a word the corpus does not consider part of
    general English, which includes both narrow terms (`blockchain`) and the
    everyday concrete nouns the list simply omits (`apple`).
    """
    head = headword(writing)
    return _rank_map().get(head) if head else None


def is_inflection(writing: str | None) -> bool:
    """Whether this spelling is a form of some other entry — `drove` for
    `drive`. Such rows are catalogue noise: they carry no meaning the headword
    doesn't already carry, and each one takes a slot in the learner's pool."""
    head = headword(writing)
    return head is not None and head != (writing or "").strip().lower()
