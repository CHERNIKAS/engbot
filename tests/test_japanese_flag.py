from __future__ import annotations

from app.bot.keyboards.onboarding import tracks_picker_kb
from app.domain.enums import LearningTrack, enabled_tracks


def test_enabled_tracks_excludes_japanese_by_default():
    assert enabled_tracks(False) == [LearningTrack.ENGLISH]


def test_enabled_tracks_includes_japanese_when_flag_on():
    assert enabled_tracks(True) == [LearningTrack.ENGLISH, LearningTrack.JAPANESE]


def test_onboarding_picker_hides_japanese_when_flag_off():
    selected = {LearningTrack.ENGLISH}
    kb = tracks_picker_kb(selected, allowed=enabled_tracks(False))
    button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("English" in t for t in button_texts)
    assert not any("Japanese" in t for t in button_texts), button_texts


def test_onboarding_picker_shows_japanese_when_flag_on():
    selected = {LearningTrack.ENGLISH}
    kb = tracks_picker_kb(selected, allowed=enabled_tracks(True))
    button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Japanese" in t for t in button_texts)
