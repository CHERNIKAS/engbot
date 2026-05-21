from __future__ import annotations

import pytest

from app.infrastructure.example_provider.local_json import LocalJsonExampleProvider


async def test_known_word_has_example():
    provider = LocalJsonExampleProvider()
    example = await provider.get_example("persistent")
    assert example is not None
    assert "persistent" in example.lower()


async def test_case_insensitive_lookup():
    provider = LocalJsonExampleProvider()
    assert (await provider.get_example("DEPLOY")) is not None


async def test_unknown_word_returns_none():
    provider = LocalJsonExampleProvider()
    assert await provider.get_example("zxcvbnmqwerty") is None
