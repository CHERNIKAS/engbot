from __future__ import annotations

import pytest

from app.bot.callbacks.schema import StudyCB
from app.bot.keyboards.study import quiz_kb


TELEGRAM_CALLBACK_LIMIT = 64


def test_quiz_callback_uses_index_not_translation_text():
    """Quiz answers must be encoded as q0..q3 indices, not the translation text.
    Otherwise a long translation would blow the 64-byte limit *and* break on
    aiogram's `:` field separator if the text contains a colon."""
    long_translation = "невероятно длинный перевод с двоеточием: и пробелами"
    version = "abcd"
    kb = quiz_kb(
        options=[long_translation, "вариант B", "вариант C", "вариант D"],
        version=version,
        user_word_id=123456,
    )
    quiz_buttons = kb.inline_keyboard[0:4]  # first 4 rows are options
    payloads = [btn[0].callback_data for btn in quiz_buttons]
    # Each answer must look like `st:answer:::q0:abcd` — no translation text.
    for idx, payload in enumerate(payloads):
        assert long_translation not in payload, (
            f"Option {idx} embeds full translation in callback_data: {payload}"
        )
        assert f"q{idx}" in payload


def test_quiz_callback_fits_telegram_64_byte_limit():
    """Even with the largest plausible user_word_id and longest version token,
    the packed quiz answer callback must be ≤ 64 bytes."""
    version = "abcdefgh"  # generous upper bound
    payload = StudyCB(
        action="answer",
        mode="quiz",
        scope="goal",
        scope_ref_id=2_147_483_647,  # int32 max
        answer="q3",
        v=version,
    ).pack()
    assert len(payload.encode("utf-8")) <= TELEGRAM_CALLBACK_LIMIT, (
        f"Quiz callback exceeds 64 bytes: {len(payload.encode('utf-8'))} bytes — {payload!r}"
    )


def test_quiz_callback_can_be_parsed_back():
    payload = StudyCB(action="answer", answer="q2", v="abcd").pack()
    parsed = StudyCB.unpack(payload)
    assert parsed.action == "answer"
    assert parsed.answer == "q2"
    assert parsed.v == "abcd"


def test_quiz_callback_handler_decodes_index_to_option():
    """Sanity: the consumer side of the contract — answer='q{n}' must map by
    index into snapshot.quiz_options. Long option text never crosses the wire."""
    options = ["длинный вариант 1", "длинный вариант 2", "длинный вариант 3", "длинный вариант 4"]
    payload = StudyCB(action="answer", answer="q2", v="x").pack()
    parsed = StudyCB.unpack(payload)
    assert parsed.answer.startswith("q")
    idx = int(parsed.answer[1:])
    assert options[idx] == "длинный вариант 3"
