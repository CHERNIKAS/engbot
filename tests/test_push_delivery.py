"""F1-F4 delivery fixes: backoff retry, weighted stream order (grammar minority)."""
from __future__ import annotations

import random
from collections import Counter

from app.services.push_service import (
    PUSH_MAX_ATTEMPTS,
    STREAM_WEIGHTS,
    _retry_after,
    _weighted_order,
)


def test_retry_after_backs_off_10_20_40():
    # ±20% jitter, so check the bands.
    assert 8 * 60 <= _retry_after(1) <= 12 * 60
    assert 16 * 60 <= _retry_after(2) <= 24 * 60
    assert 32 * 60 <= _retry_after(3) <= 48 * 60
    # capped at 40 min
    assert 32 * 60 <= _retry_after(9) <= 48 * 60


def test_max_attempts_is_small():
    assert PUSH_MAX_ATTEMPTS == 3  # a few nudges, then drop


def test_weighted_order_is_a_permutation():
    streams = ["repeat", "review", "new", "grammar"]
    out = _weighted_order(streams)
    assert sorted(out) == sorted(streams)


def test_weighted_order_grammar_is_minority_for_starved_user():
    """The reported bug: 0 mastered + full pool => only repeat & grammar live.
    Grammar must NOT win ~50%; with weights 60 vs 15 it should be ~20% of the
    time it appears before repeat."""
    random.seed(0)
    eligible = ["repeat", "grammar"]  # review/new dead for user 1
    first = Counter(_weighted_order(eligible)[0] for _ in range(4000))
    grammar_share = first["grammar"] / 4000
    assert 0.15 <= grammar_share <= 0.27, grammar_share  # ~15/(60+15)=20%, not 50%


def test_weights_keep_words_dominant():
    word_w = STREAM_WEIGHTS["repeat"] + STREAM_WEIGHTS["review"] + STREAM_WEIGHTS["new"]
    assert STREAM_WEIGHTS["grammar"] < word_w / 4  # grammar is a small slice
