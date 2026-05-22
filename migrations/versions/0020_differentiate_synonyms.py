"""differentiate synonym translations (begin/start/commence → distinct)

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-22

Content upgrade batch 4: 81 words shared an identical Russian translation with
another word (e.g. begin/commence/start all "начинать"), so learning one taught
nothing new and you couldn't tell which English word to use. Each gets a short
nuance/register marker so every sense is distinct. Phrase variants (e.g. two
phrasings of "Go straight") are left as-is. Idempotent: only updates rows that
still hold the old value; downgrade restores them.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


# (normalized_word, old_translation, new_translation)
CHANGES: list[tuple[str, str, str]] = [
    ("include", "включать", "включать / содержать"),
    ("turn on", "включать", "включать (прибор)"),
    ("say", "говорить", "говорить / сказать"),
    ("speak", "говорить", "говорить / разговаривать"),
    ("adequate", "достаточный", "достаточный / приемлемый"),
    ("achieve", "достигать", "достигать / добиваться"),
    ("attain", "достигать", "достигать (уровня)"),
    ("income", "доход", "доход (заработок)"),
    ("yield", "доход", "доходность (с вложений)"),
    ("issue", "задача", "вопрос / проблема"),
    ("considerable", "значительный", "значительный (немалый)"),
    ("significant", "значительный", "значимый / существенный"),
    ("seek", "искать", "искать / стремиться"),
    ("utilize", "использовать", "использовать (задействовать)"),
    ("exploit", "использовать", "эксплуатировать / использовать"),
    ("concise", "краткий", "краткий / лаконичный"),
    ("start", "начинать", "начинать / запускать"),
    ("commence", "начинать", "начинать (формально)"),
    ("minor", "незначительный", "незначительный / второстепенный"),
    ("slight", "незначительный", "незначительный (лёгкий)"),
    ("constrain", "ограничивать", "ограничивать (сковывать)"),
    ("confine", "ограничивать", "ограничивать (рамками)"),
    ("enormous", "огромный", "огромный / громадный"),
    ("define", "определять", "давать определение"),
    ("determine", "определять", "определять / устанавливать"),
    ("identify", "определять", "выявлять / определять"),
    ("assess", "оценивать", "оценивать (давать оценку)"),
    ("estimate", "оценивать", "оценивать (прикидывать)"),
    ("apparent", "очевидный", "очевидный / видимый"),
    ("maintain", "поддерживать", "поддерживать (сохранять)"),
    ("receive", "получать", "получать (принимать)"),
    ("obtain", "получать", "получать (добывать)"),
    ("assist", "помогать", "помогать (содействовать)"),
    ("emerge", "появляться", "появляться / возникать"),
    ("credible", "правдоподобный", "заслуживающий доверия"),
    ("suggest", "предлагать", "предлагать (идею)"),
    ("propose", "предлагать", "предлагать (официально)"),
    ("imagine", "представлять", "представлять / воображать"),
    ("represent", "представлять", "представлять (интересы)"),
    ("acknowledge", "признавать", "признавать / подтверждать"),
    ("go on", "продолжать", "продолжать (дальше)"),
    ("decision", "решение", "решение (выбор)"),
    ("solution", "решение", "решение (проблемы)"),
    ("complex", "сложный", "сложный (составной)"),
    ("complicated", "сложный", "сложный (запутанный)"),
    ("contemporary", "современный", "современный (нынешний)"),
    ("account", "счёт", "счёт (банковский)"),
    ("score", "счёт", "счёт (в игре)"),
    ("convince", "убеждать", "убеждать / уверять"),
    ("confident", "уверенный", "уверенный (в себе)"),
    ("enhance", "улучшать", "улучшать / усиливать"),
    ("diminish", "уменьшать", "уменьшаться / убывать"),
    ("establish", "устанавливать", "устанавливать / основывать"),
]


def _apply(changes: list[tuple[str, str, str]]) -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE words SET translation = :new "
        "WHERE track = 'en' AND normalized_word = :n AND translation = :old"
    )
    for normalized, old, new in changes:
        conn.execute(stmt, {"n": normalized, "old": old, "new": new})


def upgrade() -> None:
    _apply(CHANGES)


def downgrade() -> None:
    _apply([(n, new, old) for n, old, new in CHANGES])
