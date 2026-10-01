"""Sorting a theme's words into "already know" and "teach me" in one pass.

The bot has always had a per-card «я знаю» button, and it works — but a theme
holds dozens of words that arrive one a day, so using it means making the same
judgement forty times across six weeks. Most people will not, and the theme
teaches them `work` and `house` anyway.

The batch screen asks once, for a screenful at a time. It is the part of ReWord
worth copying: relevance is decided by the learner up front rather than
inferred by the picker afterwards, and it takes twenty seconds.

Marking a word does not delete it. It graduates — the same outcome as answering
the card and pressing «уже уверенно знаю» — so it stays in the occasional
refresh rotation. Claiming to know a word is not proof, and the cheapest way to
find out you were wrong is to be asked about it in a month.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, replace

# One screenful. Fifteen buttons is already a long keyboard on a phone; the
# next batch arrives when the theme's unmarked words run low, so a large theme
# is several short screens rather than one endless list.
BATCH_SIZE = 15


@dataclass(frozen=True)
class TriageState:
    """Which of the offered words are currently marked as known.

    Immutable: the state round-trips through Redis between taps, and a helper
    that mutated in place would work locally and lose the change on the way out.
    """

    known: tuple[int, ...] = ()

    def toggle(self, user_word_id: int) -> "TriageState":
        if user_word_id in self.known:
            return replace(self, known=tuple(i for i in self.known if i != user_word_id))
        return replace(self, known=self.known + (user_word_id,))

    def marked(self, user_word_id: int) -> bool:
        return user_word_id in self.known

    def to_dict(self) -> dict:
        return {"known": list(self.known)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "TriageState":
        return cls(known=tuple(int(i) for i in (data or {}).get("known") or ()))


def button_label(writing: str, translation: str, marked: bool) -> str:
    """One word as a button.

    The translation is shown rather than hidden behind a reveal: the learner is
    being asked whether they know this word, and answering that honestly needs
    to know which sense is meant — `charge` is a different question depending on
    whether it means «заряд» or «плата».
    """
    mark = "✅ " if marked else ""
    gloss = (translation or "").split("/")[0].strip()
    label = f"{mark}{writing} — {gloss}" if gloss else f"{mark}{writing}"
    return label[:60]


def render(theme_title: str, offered: int, known: int) -> str:
    """The batch screen's text. The buttons carry the words; this carries only
    what the screen is for, because the keyboard is already tall.

    The theme name is not repeated here — it rides in the card head now, and
    printing it twice with the same icon read as a formatting slip.
    """
    return (
        "Отметь слова, которые уже знаешь — их учить не будем.\n"
        f"<i>Отмечено {known} из {offered}.</i>"
    )


def render_summary(theme_title: str, known: int, learning: int) -> str:
    """What the screen collapses into once it is done, so the chat keeps a line
    rather than a dead keyboard."""
    return (
        f"🗂 <b>{html.escape(theme_title)}</b>\n"
        f"Знаешь: {known} · учим: {learning}"
    )
