"""The second thousand of the corpus list, checked before it reaches anyone.

Generated content has claimed «100% accepted» three times in this project and
been wrong all three. So the batch is verified here against the same rules the
first thousand obeys, and the checks that matter are the ones a generator
cannot see: a translation already spoken for, a word the stoplist owns, a rank
outside the band it claims to fill.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.function_words import FUNCTION_WORDS
from app.domain.levels import LEVELS

DATA = (
    Path(__file__).resolve().parent.parent
    / "app" / "infrastructure" / "data" / "ngsl_band2.json"
)

ROWS = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_every_word_sits_in_the_band_it_claims():
    """A rank outside 1001–2000 means the word belongs to another band, and the
    level formula counts bands — a stray rank would move somebody's level."""
    for row in ROWS:
        assert 1001 <= row["ngsl_rank"] <= 2000, row


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_no_word_appears_twice():
    words = [r["w"].lower() for r in ROWS]
    assert len(words) == len(set(words))


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_no_two_words_share_a_translation():
    """The forward card survives it — `quiz_distractors` drops a distractor
    that shares a meaning with the answer — but the reverse card asks for the
    English from the Russian, and «серый → ?» has no right answer when both
    greys are in the catalogue."""
    seen: dict[str, str] = {}
    for row in ROWS:
        key = row["translation"].strip().lower()
        assert key not in seen, f"«{key}»: {seen.get(key)} и {row['w']}"
        seen[key] = row["w"]


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_the_stoplist_is_respected():
    """Function words are taught by grammar, not as cards. Four of them
    (`unless`, `onto`, `ought`, `unlike`) sit in this band and were dropped."""
    stop = {w.lower() for w in FUNCTION_WORDS}
    for row in ROWS:
        assert row["w"].lower() not in stop, row["w"]


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_every_entry_is_usable_as_a_card():
    for row in ROWS:
        assert row["translation"].strip(), row["w"]
        assert row["level"] in LEVELS, row
        assert row["w"].strip() and " " not in row["w"].strip(), row["w"]


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_translations_are_russian():
    """A Latin translation means the model echoed the prompt back."""
    for row in ROWS:
        assert any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in row["translation"]), row


@pytest.mark.skipif(not ROWS, reason="band 2 not generated yet")
def test_the_band_is_actually_filled():
    """495 words were there before; this is what closes the band. If the count
    drops sharply, something went wrong upstream and the band is half-empty
    again — which is the state that made the second year impossible."""
    assert len(ROWS) >= 500
