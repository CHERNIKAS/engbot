"""The second thousand of the corpus list, checked before it reaches anyone.

Generated content has claimed «100% accepted» three times in this project and
been wrong all three. So the batch is verified here against the same rules the
first thousand obeys, and the checks that matter are the ones a generator
cannot see: a translation already spoken for, a word the stoplist owns, a rank
outside the band it claims to fill.
"""
from __future__ import annotations

import collections
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


def _migration():
    import importlib.util

    path = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "0061_catalogue_cleanup.py"
    spec = importlib.util.spec_from_file_location("m0061", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ngsl_ranks():
    import csv

    path = (
        Path(__file__).resolve().parent.parent
        / "app" / "infrastructure" / "data" / "ngsl_rank.csv"
    )
    return {r["lemma"].strip().lower(): int(r["rank"]) for r in csv.DictReader(path.open())}


def test_every_rank_the_migration_assigns_belongs_to_that_lemma():
    """A rank belongs to the lemma NGSL lists, not to anything spelled like it.
    Nine words were given ranks by hand here, and the first draft had them from
    memory — all nine were wrong."""
    ngsl = _ngsl_ranks()
    for writing, rank in _migration().MISSING_RANK:
        assert ngsl.get(writing) == rank, writing


def test_no_stolen_rank_is_left_with_the_derived_word():
    """The 32 pairs this migration unpicks: in each one a derived form carried
    its headword's rank — `thought` held 47, which is `think`'s. The derived
    word must not be the lemma at that rank in NGSL, or we would be clearing
    the rank from its rightful owner."""
    ngsl = _ngsl_ranks()
    for derived, rank, _freq in _migration().STOLEN_RANKS:
        assert ngsl.get(derived) != rank, f"{derived} действительно держит {rank}"


def test_the_generated_words_do_not_reuse_a_rank_being_freed():
    """The new words take the ranks the derived forms are giving up — `camp`
    gets 1165 from `camping`. Two words must not end up claiming one rank."""
    freed = {rank for _d, rank, _f in _migration().STOLEN_RANKS}
    taken = collections.Counter(r["ngsl_rank"] for r in ROWS)
    for rank in freed:
        assert taken[rank] <= 1, rank


def test_inflections_are_only_words_without_a_meaning_of_their_own():
    """`children` and `feet` are plurals and nothing else, and the plural topic
    drills them. `tired` and `interesting` are not on this list even though they
    look like forms — they have meanings of their own, and the criterion is the
    meaning, not the spelling."""
    marked = set(_migration().INFLECTIONS)
    assert {"children", "feet"} <= marked
    assert not marked & {"tired", "interesting", "building", "shoes", "thought"}
