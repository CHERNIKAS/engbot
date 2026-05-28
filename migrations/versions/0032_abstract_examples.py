"""words: abstract_example_en + abstract_example_ru columns.

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-28

Context examples shown ON the push card. The PAIRED example uses a
synonym / paraphrase so the target word itself doesn't appear in the
sentence — gives the user real context without leaking the answer.
Both nullable: when an abstract version can't be authored cleanly we
simply don't show an example for that word.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("words", sa.Column("abstract_example_en", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("abstract_example_ru", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("words", "abstract_example_ru")
    op.drop_column("words", "abstract_example_en")
