from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks.schema import DeleteCB
from app.bot.handlers.my_words import DELETE_SCREEN_KIND, on_delete_confirm
from app.services.screen_service import ScreenVersionService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


async def test_stale_delete_callback_does_not_delete_word():
    """If a user clicks the confirm button on an old delete prompt — version
    mismatch — the word must NOT be deleted."""
    redis = FakeRedis()
    screen = ScreenVersionService(redis)  # type: ignore[arg-type]
    # Current valid version for this user/screen.
    await screen.bump(user_id=1, kind=DELETE_SCREEN_KIND)
    # The user is clicking a button from a previous render with a different token.
    stale_v = "stale-v"

    user = SimpleNamespace(id=1)
    callback_data = DeleteCB(action="confirm", user_word_id=42, flow="mw", v=stale_v)

    cb = MagicMock(spec=CallbackQuery)
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    # Spy: this repo must NOT be hit. We use a session that explodes on access.
    class ExplodingSession:
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - guard
            raise AssertionError(
                f"Session must not be touched for stale callback (got: {name!r})"
            )

    state_service = MagicMock()
    state_service.clear = AsyncMock()
    user_track_service = MagicMock()
    user_track_service.list_active = AsyncMock(return_value=[])

    await on_delete_confirm(
        query=cb,
        callback_data=callback_data,
        user=user,
        current_track="en",  # not used for stale early-return
        session=ExplodingSession(),  # would explode if reached
        user_track_service=user_track_service,
        state_service=state_service,
        study_session=MagicMock(),
        screen_service=screen,
    )

    cb.answer.assert_called_once()
    assert "устарело" in cb.answer.call_args.args[0].lower()
    state_service.clear.assert_not_called()
    cb.message.edit_text.assert_not_called()


async def test_fresh_delete_callback_proceeds_past_stale_guard():
    """Sanity: a current version token clears the stale guard. We don't assert
    DB writes (those need real session); we just confirm the guard lets the
    handler proceed past the early-return."""
    redis = FakeRedis()
    screen = ScreenVersionService(redis)  # type: ignore[arg-type]
    fresh_v = await screen.bump(user_id=1, kind=DELETE_SCREEN_KIND)

    user = SimpleNamespace(id=1)
    callback_data = DeleteCB(action="confirm", user_word_id=42, flow="mw", v=fresh_v)

    cb = MagicMock(spec=CallbackQuery)
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    # Build a session/service stack that simulates "word deleted, no categories".
    # The handler proceeds: deletes, clears state, lists categories, edits text.
    class FakeUserWordRepo:
        async def delete(self, *_a, **_kw) -> None:
            self.deleted = True

    class FakeCategoryService:
        async def list_user_categories(self, *_a, **_kw):
            return []

        async def counts(self, *_a, **_kw):
            return {}

    # Build the most minimal stand-in for AsyncSession that the handler's
    # downstream code path consumes via factory wrappers. Easiest path: stub
    # the wrappers themselves via monkeypatching at the handler module level.
    import app.bot.handlers.my_words as mw

    deleted = {"v": False}

    class _StubRepo:
        def __init__(self, _session) -> None:
            pass

        async def delete(self, _id) -> None:
            deleted["v"] = True

    class _StubCatRepo:
        def __init__(self, _session) -> None:
            pass

    class _StubCatService:
        def __init__(self, _repo) -> None:
            pass

        async def list_user_categories(self, _user_id, _track):
            return []

        async def counts(self, _user_id, _track):
            return {}

    monkey_attrs = [
        ("UserWordRepository", mw.UserWordRepository, _StubRepo),
        ("CategoryRepository", mw.CategoryRepository, _StubCatRepo),
        ("CategoryService", mw.CategoryService, _StubCatService),
    ]
    originals = {}
    for name, original, replacement in monkey_attrs:
        originals[name] = original
        setattr(mw, name, replacement)
    try:
        state_service = MagicMock()
        state_service.clear = AsyncMock()
        user_track_service = MagicMock()
        user_track_service.list_active = AsyncMock(return_value=[])

        await on_delete_confirm(
            query=cb,
            callback_data=callback_data,
            user=user,
            current_track="en",
            session=MagicMock(),
            user_track_service=user_track_service,
            state_service=state_service,
            study_session=MagicMock(),
            screen_service=screen,
        )
    finally:
        for name, original, _ in monkey_attrs:
            setattr(mw, name, original)

    assert deleted["v"] is True
    state_service.clear.assert_awaited()
