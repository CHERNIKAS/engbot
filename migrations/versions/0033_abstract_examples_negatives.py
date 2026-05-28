"""abstract examples for negatives_contractions: 16 word entries.

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-28

First batch demoing the abstract-example format on the push card. Each
pair uses a synonym / paraphrase so the target word (haven't, can't, …)
does NOT appear in the English sentence, with a matching Russian translation
under it. Idempotent — only fills when both fields are NULL/empty.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


# normalized_word -> (abstract English with synonym, Russian translation).
PAIRS: dict[str, tuple[str, str]] = {
    "haven't": ("She still hasn't called me back.", "Она мне до сих пор не перезвонила."),
    "hasn't":  ("The shop doesn't stock that brand.", "В магазине нет этой марки."),
    "don't":   ("I refuse to eat seafood.",         "Я отказываюсь есть морепродукты."),
    "doesn't": ("He never goes out on weekends.",   "Он никогда не выходит на выходных."),
    "can't":   ("She is unable to swim.",           "Она не умеет плавать."),
    "won't":   ("I refuse to be late again.",       "Я больше не хочу опаздывать."),
    "isn't":   ("This solution simply doesn't fit.", "Это решение просто не подходит."),
    "aren't":  ("These ideas just don't match our plan.", "Эти идеи просто не подходят под наш план."),
    "wasn't":  ("He missed the meeting yesterday.", "Он пропустил вчерашнюю встречу."),
    "weren't": ("Many guests skipped the party.",   "Многие гости пропустили вечеринку."),
    "didn't":  ("She forgot to read the message.",  "Она забыла прочитать сообщение."),
    "couldn't": ("He was unable to sleep all night.", "Он не смог уснуть всю ночь."),
    "wouldn't": ("She refused to help us.",         "Она отказалась нам помочь."),
    "shouldn't": ("It's a bad idea to skip breakfast.", "Пропускать завтрак — плохая идея."),
    "mustn't": ("It is forbidden to smoke here.",   "Здесь запрещено курить."),
    "hadn't":  ("She had never met him before that day.", "До того дня она его никогда не встречала."),
}


def upgrade() -> None:
    conn = op.get_bind()
    for normalized, (en, ru) in PAIRS.items():
        conn.execute(
            sa.text(
                "UPDATE words SET abstract_example_en = :en, abstract_example_ru = :ru "
                "WHERE track = 'en' AND normalized_word = :n "
                "AND (abstract_example_en IS NULL OR abstract_example_en = '') "
                "AND (abstract_example_ru IS NULL OR abstract_example_ru = '')"
            ),
            {"en": en, "ru": ru, "n": normalized},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for normalized, (en, ru) in PAIRS.items():
        conn.execute(
            sa.text(
                "UPDATE words SET abstract_example_en = NULL, abstract_example_ru = NULL "
                "WHERE track = 'en' AND normalized_word = :n "
                "AND abstract_example_en = :en AND abstract_example_ru = :ru"
            ),
            {"en": en, "ru": ru, "n": normalized},
        )
