from __future__ import annotations

import pytest

from app.domain.pos import infer_part_of_speech


@pytest.mark.parametrize(
    "translation,expected",
    [
        # verbs (incl. reflexive and multi-sense / clarified forms)
        ("забывать", "verb"),
        ("идти / ехать", "verb"),
        ("делать / создавать", "verb"),
        ("соглашаться", "verb"),
        ("решать (проблему)", "verb"),
        ("беречь", "verb"),
        # adjectives (the basic A1/A2 ones must be caught, incl. -ий)
        ("хороший", "adj"),
        ("большой", "adj"),
        ("маленький", "adj"),
        ("трудный", "adj"),
        ("дорогой", "adj"),
        ("похожий", "adj"),
        # nouns — including the -ие/-ия neuter/fem nouns that must NOT read as adj
        ("время", "noun"),
        ("знание", "noun"),
        ("решение", "noun"),
        ("ситуация", "noun"),
        ("возможность", "noun"),
        ("друг", "noun"),
        ("вода", "noun"),
        # not inferable -> None
        ("ждать с нетерпением", None),
        ("окружающая среда", None),
        ("сейчас", None),
        ("сегодня", None),
        ("", None),
        (None, None),
    ],
)
def test_infer_part_of_speech(translation, expected):
    assert infer_part_of_speech(translation) == expected
