"""Quiz option sanitizer: Latin hints inside a gloss must not reach the card."""
from __future__ import annotations

from app.domain.quiz_text import strip_latin_hints


def test_strips_contraction_hint():
    assert strip_latin_hints("не являются (сокращение от are not)") == "не являются"
    assert strip_latin_hints("не могу (сокращение от cannot)") == "не могу"


def test_strips_irregular_form_hint():
    assert strip_latin_hints("стал (прошедшее от become)") == "стал"
    assert strip_latin_hints("был (причастие от be)") == "был"


def test_keeps_cyrillic_parenthetical():
    assert strip_latin_hints("доля (крипто)") == "доля (крипто)"
    assert strip_latin_hints("ставка (в казино)") == "ставка (в казино)"


def test_plain_gloss_untouched():
    assert strip_latin_hints("забывать") == "забывать"
    assert strip_latin_hints("хранить / держать") == "хранить / держать"


def test_all_hint_gloss_falls_back_to_original():
    # Pathological: nothing left after stripping -> better the leak than blank.
    assert strip_latin_hints("(form of be)") == "(form of be)"


def test_empty_safe():
    assert strip_latin_hints("") == ""
