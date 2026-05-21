from __future__ import annotations

from typing import Protocol


class ExampleProvider(Protocol):
    async def get_example(self, normalized_word: str) -> str | None: ...
