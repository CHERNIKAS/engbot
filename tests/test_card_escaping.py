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


def test_the_card_never_puts_its_own_question_mark_on_the_english():
    """«Что значит <b>Sounds good</b>?» read as a question about "Sounds good?"
    — the card's punctuation looked like the phrase's own, and on a phrase that
    really is a question the two were indistinguishable (2026-10-29)."""
    from app.bot.texts import PUSH_CARD

    assert not PUSH_CARD.rstrip().endswith("?")
    assert "{word}</b>?" not in PUSH_CARD
    rendered = PUSH_CARD.format(word="Sounds good")
    assert "?" not in rendered
    # A phrase that is itself a question keeps its own mark, and it is the only
    # one on the card.
    assert PUSH_CARD.format(word="How are you?").count("?") == 1
