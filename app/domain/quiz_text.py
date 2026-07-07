from __future__ import annotations

import re

# A parenthetical that contains at least one Latin letter — a gloss hint like
# «стал (прошедшее от become)» or «не могу (сокращение от cannot)». Shown on a
# quiz card it hands over the answer: the option literally contains the English
# word being asked about. Cyrillic parentheticals («доля (крипто)») are kept —
# they clarify meaning without leaking.
_PAREN_WITH_LATIN = re.compile(r"\s*\([^()]*[A-Za-z][^()]*\)")


def strip_latin_hints(translation: str) -> str:
    """A translation as it may appear on a quiz card BEFORE the user answers.
    Removes parenthetical hints containing Latin letters; the full gloss stays
    in the word's detail card, where spoiling is not a concern."""
    if not translation:
        return translation
    cleaned = " ".join(_PAREN_WITH_LATIN.sub("", translation).split())
    return cleaned or translation
