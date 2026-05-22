from __future__ import annotations

from app.bot.handlers.study import _card_text
from app.domain.study_drill import STAGE_QUIZ, STAGE_TYPE
from app.services.study_session_service import CardView


def _view(stage: str, writing: str, translation: str) -> CardView:
    return CardView(
        uw_id=1,
        stage=stage,
        writing=writing,
        translation=translation,
        example=None,
        options=["x"],
        learned=0,
        total=1,
    )


def test_typing_card_escapes_translation():
    # A translation with HTML-special chars must not break the HTML message.
    text = _card_text(_view(STAGE_TYPE, "hold", "a < b & c"), romaji_enabled=True)
    assert "a &lt; b &amp; c" in text
    assert "a < b & c" not in text  # raw, unescaped form must be gone


def test_quiz_card_escapes_writing():
    text = _card_text(_view(STAGE_QUIZ, "A&B", "перевод"), romaji_enabled=True)
    assert "A&amp;B" in text
    assert "<b>A&B</b>" not in text
