from __future__ import annotations

import json

from app.services.level_tagger import RESPONSE_SCHEMA, SYSTEM_PROMPT, LevelTaggerService


def _response(rows) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(rows)}]}}]}


def test_parse_reads_a_well_formed_batch():
    parsed = LevelTaggerService._parse(
        _response([{"id": 7, "level": "B1", "freq": 2}, {"id": 9, "level": "A1", "freq": 1}])
    )
    assert parsed == {7: ("B1", 2), 9: ("A1", 1)}


def test_parse_drops_a_level_outside_the_scale():
    """A hallucinated level is a model slip — skip that word, keep the rest."""
    parsed = LevelTaggerService._parse(
        _response([{"id": 1, "level": "D9", "freq": 2}, {"id": 2, "level": "A2", "freq": 1}])
    )
    assert parsed == {2: ("A2", 1)}


def test_parse_clamps_frequency_into_range():
    parsed = LevelTaggerService._parse(
        _response([{"id": 1, "level": "A1", "freq": 99}, {"id": 2, "level": "A1", "freq": -4}])
    )
    assert parsed == {1: ("A1", 5), 2: ("A1", 1)}


def test_parse_defaults_a_missing_frequency_to_the_middle():
    assert LevelTaggerService._parse(_response([{"id": 1, "level": "B1"}])) == {1: ("B1", 3)}


def test_parse_skips_rows_with_an_unusable_id():
    parsed = LevelTaggerService._parse(
        _response([{"level": "A1", "freq": 1}, {"id": "x", "level": "A1", "freq": 1}])
    )
    assert parsed == {}


def test_parse_rejects_a_response_that_is_not_a_batch():
    for bad in ({}, {"candidates": []}, _response({"not": "a list"})):
        try:
            result = LevelTaggerService._parse(bad)
        except ValueError:
            continue
        assert result == {}, bad


def test_parse_raises_on_non_json_text():
    bad = {"candidates": [{"content": {"parts": [{"text": "sorry, I can't"}]}}]}
    try:
        LevelTaggerService._parse(bad)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_disabled_without_an_api_key(monkeypatch):
    svc = LevelTaggerService.__new__(LevelTaggerService)
    svc._settings = type("S", (), {"gemini_api_key": ""})()
    assert svc.enabled is False
    svc._settings = type("S", (), {"gemini_api_key": "k"})()
    assert svc.enabled is True


def test_prompt_and_schema_stay_in_sync_with_the_scale():
    """The offline backfill script imports both from here — a drift would grade
    new words on a different scale than the catalogue."""
    from app.domain.levels import LEVELS

    assert RESPONSE_SCHEMA["items"]["properties"]["level"]["enum"] == list(LEVELS)
    for level in ("A1", "A2", "B1", "B2"):
        assert f"\n{level}: " in SYSTEM_PROMPT  # calibration anchors present
