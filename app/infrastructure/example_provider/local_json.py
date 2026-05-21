from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).parent / "data" / "examples.json"


class LocalJsonExampleProvider:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not self._path.exists():
            self._data = {}
        else:
            raw: Any = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data = {str(k).lower(): str(v) for k, v in raw.items() if v}
        self._loaded = True

    async def get_example(self, normalized_word: str) -> str | None:
        self._load()
        return self._data.get(normalized_word.lower())
