"""Heal word progress: replay review history under the current SR rules.

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-08

Until 2026-06-17 a wrong answer wiped repetitions_count to zero; after that it
dropped 3. Words punished under those harsher rules still carry the damage
(prod showed words with 7 correct answers of 8 sitting at 1/10). This replays
each active word's full word_reviews history under the rules shipping with
this revision (correct +1, wrong -2, mastery at 10) and keeps the better of
replayed vs current progress. Words whose replay crosses the mastery bar are
promoted to mastered outright.

Deterministic and idempotent: re-running changes nothing (max() of the same
replay). Downgrade is a no-op — the old value was the product of a bug; there
is nothing truthful to restore.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

MASTERED_AT = 10
LAPSE_DROP = 2
MASTERY_SCORE_MAX = 5.0


def _replay(results: list[str]) -> int:
    """Fold a word's review history under the current rules. Once the bar is
    crossed the word counts as mastered — later reviews can't demote it (the
    runtime engine treats mastered words the same way)."""
    reps = 0
    for result in results:
        if result in ("correct", "normal", "easy"):
            reps += 1
            if reps >= MASTERED_AT:
                return reps
        elif result == "wrong":
            reps = max(0, reps - LAPSE_DROP)
        # hard: reps unchanged
    return reps


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT uw.id, uw.repetitions_count, wr.result
            FROM user_words uw
            JOIN word_reviews wr ON wr.user_word_id = uw.id
            WHERE uw.archived = false
              AND uw.status IN ('learning', 'review')
            ORDER BY uw.id, wr.id
            """
        )
    ).fetchall()

    history: dict[int, tuple[int, list[str]]] = {}
    for uw_id, current_reps, result in rows:
        history.setdefault(uw_id, (current_reps, []))[1].append(result)

    for uw_id, (current_reps, results) in history.items():
        healed = max(_replay(results), current_reps or 0)
        if healed >= MASTERED_AT:
            bind.execute(
                sa.text(
                    """
                    UPDATE user_words
                    SET repetitions_count = :reps, status = 'mastered',
                        mastery_score = :score
                    WHERE id = :id
                    """
                ),
                {"reps": healed, "score": MASTERY_SCORE_MAX, "id": uw_id},
            )
        elif healed != (current_reps or 0):
            bind.execute(
                sa.text(
                    "UPDATE user_words SET repetitions_count = :reps WHERE id = :id"
                ),
                {"reps": healed, "id": uw_id},
            )


def downgrade() -> None:
    pass
