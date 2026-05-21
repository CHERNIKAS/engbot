from __future__ import annotations

from types import SimpleNamespace

from app.bot.keyboards.main_menu import main_menu_kb
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


def test_main_menu_switcher_hides_japanese_track_when_flag_off(monkeypatch):
    """Even if a stale UserTrack(track='ja', is_active=True) exists in DB
    (e.g. from a pre-flag onboarding), the switcher must NOT render it."""
    from app.bot.keyboards import main_menu as mm

    monkeypatch.setattr(
        mm,
        "get_settings",
        lambda: SimpleNamespace(enable_japanese=False),
    )

    active = [
        SimpleNamespace(track="en", is_active=True),
        SimpleNamespace(track="ja", is_active=True),
    ]
    kb = main_menu_kb(active, LearningTrack.ENGLISH)
    callback_payloads = [
        btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data
    ]
    # No track-switch button to Japanese should appear.
    assert not any("mm:track:ja" in c for c in callback_payloads), callback_payloads
    # And since only one allowed track remains, no switcher row at all.
    assert not any("mm:track:" in c for c in callback_payloads)


def test_main_menu_switcher_shows_both_when_flag_on(monkeypatch):
    from app.bot.keyboards import main_menu as mm

    monkeypatch.setattr(
        mm,
        "get_settings",
        lambda: SimpleNamespace(enable_japanese=True),
    )

    active = [
        SimpleNamespace(track="en", is_active=True),
        SimpleNamespace(track="ja", is_active=True),
    ]
    kb = main_menu_kb(active, LearningTrack.ENGLISH)
    callback_payloads = [
        btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data
    ]
    assert any("mm:track:en" in c for c in callback_payloads)
    assert any("mm:track:ja" in c for c in callback_payloads)
