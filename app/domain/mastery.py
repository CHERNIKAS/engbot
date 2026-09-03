"""What "learned" means: weighted credit plus a floor of real production.

The old rule counted any correct answer toward a flat bar of 10. Two things
were wrong with it. First, most of those answers are four-option cards, so a
quarter of them can be guessed — a word could graduate without ever being
written. Second, prod showed the bar was unreachable anyway: active words
averaged 5.1 reps and peaked at 9, and the only words ever marked learned came
in through the easy path or the "I already know this" button.

So credit is now weighted by how much the answer actually proves, and mastery
additionally requires a minimum number of *typed* answers, which cannot be
guessed. The AI answer check feeds this too: it classifies a near-miss, and the
weight table — not the model — decides what that classification is worth.
"""

from __future__ import annotations

from app.domain.levels import gap

# What one answer is worth. Recognising a translation among four options is
# weak evidence; producing the word from memory is strong.
CREDIT_RECOGNITION = 0.5  # EN -> pick the translation
CREDIT_REVERSE = 0.8  # RU -> pick the English word
CREDIT_TYPED_EXACT = 1.5  # typed it correctly
CREDIT_TYPED_TYPO = 1.0  # one slip on a long word — they know it
CREDIT_TYPED_SYNONYM = 0.8  # a different valid word: real knowledge, wrong target
CREDIT_TYPED_GRAMMAR = 0.3  # right word, wrong form ("I am agree")
CREDIT_WRONG = -1.0

# Answer kinds. The typed ones are the only ones that count as production.
RECOGNITION = "recognition"
REVERSE = "reverse"
TYPED_EXACT = "typed_exact"
TYPED_TYPO = "typed_typo"
TYPED_SYNONYM = "typed_synonym"
TYPED_GRAMMAR = "typed_grammar"
WRONG = "wrong"

_CREDIT: dict[str, float] = {
    RECOGNITION: CREDIT_RECOGNITION,
    REVERSE: CREDIT_REVERSE,
    TYPED_EXACT: CREDIT_TYPED_EXACT,
    TYPED_TYPO: CREDIT_TYPED_TYPO,
    TYPED_SYNONYM: CREDIT_TYPED_SYNONYM,
    TYPED_GRAMMAR: CREDIT_TYPED_GRAMMAR,
    WRONG: CREDIT_WRONG,
}

# Kinds that prove the user can produce the word unaided. A grammar slip counts:
# they wrote the word, they just wrapped it wrong.
_PRODUCTION_KINDS = frozenset({TYPED_EXACT, TYPED_TYPO, TYPED_GRAMMAR})

# (score to reach, typed answers required) by how far the word sits above the
# user. Each target is roughly what the intended mix of cards adds up to — e.g.
# at level, three choice cards plus five typed ones. Production never drops
# below three, however easy the word: that floor is the whole point.
_TARGETS: dict[int, tuple[float, int]] = {
    -2: (5.5, 3),
    -1: (6.5, 3),
    0: (9.5, 5),
    1: (11.0, 5),
}
_TARGET_FAR = (12.5, 5)

MIN_PRODUCTION = 3


def credit(kind: str) -> float:
    """Score change for one answer. An unknown kind scores nothing rather than
    guessing a weight — a silent mis-scoring is worse than no scoring."""
    return _CREDIT.get(kind, 0.0)


def is_production(kind: str) -> bool:
    return kind in _PRODUCTION_KINDS


def target_for(word_level: str | None, user_level: str | None) -> tuple[float, int]:
    """(score target, typed answers required) for this word and this user."""
    if not word_level:
        # Untagged: treat as at-level rather than as hard, same as everywhere else.
        return _TARGETS[0]
    return _TARGETS.get(gap(word_level, user_level), _TARGET_FAR)


def apply_credit(score: float, kind: str) -> float:
    """New score after one answer, floored at zero — a run of misses shouldn't
    dig a hole the user has to climb out of before making visible progress."""
    return max(0.0, round(score + credit(kind), 2))


def is_mastered(
    score: float, production_count: int, word_level: str | None, user_level: str | None
) -> bool:
    """Both gates must pass. The score alone could be reached on choice cards;
    the production floor is what stops a guessed word from graduating."""
    target_score, needed_production = target_for(word_level, user_level)
    return score >= target_score and production_count >= needed_production
