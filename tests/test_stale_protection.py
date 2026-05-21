from __future__ import annotations

import pytest

from app.bot.callbacks.schema import (
    CategoryCB,
    DeleteCB,
    ImportCB,
    SettingsCB,
)
from app.services.screen_service import ScreenVersionService


TELEGRAM_CALLBACK_LIMIT = 64


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture
def screen() -> ScreenVersionService:
    return ScreenVersionService(FakeRedis())  # type: ignore[arg-type]


# --- version field is wired up on all destructive callback factories ---


def test_delete_callback_carries_version_field():
    payload = DeleteCB(action="confirm", user_word_id=1, flow="mw", v="abcd").pack()
    parsed = DeleteCB.unpack(payload)
    assert parsed.v == "abcd"


def test_category_callback_carries_version_field():
    payload = CategoryCB(action="pick", category_id=5, flow="add", v="abcd").pack()
    parsed = CategoryCB.unpack(payload)
    assert parsed.v == "abcd"


def test_import_callback_carries_version_field():
    payload = ImportCB(action="confirm", category_id=3, v="abcd").pack()
    parsed = ImportCB.unpack(payload)
    assert parsed.v == "abcd"


def test_settings_callback_carries_version_field():
    payload = SettingsCB(action="goal_value", value="20", v="abcd").pack()
    parsed = SettingsCB.unpack(payload)
    assert parsed.v == "abcd"


# --- screen-version service: bump/check semantics ---


async def test_screen_version_check_returns_true_for_current(screen):
    v = await screen.bump(user_id=1, kind="del_confirm")
    assert await screen.check(1, "del_confirm", v) is True


async def test_screen_version_check_returns_false_for_stale(screen):
    """Old version (from a previous render) must be rejected after a new bump."""
    old_v = await screen.bump(user_id=1, kind="del_confirm")
    new_v = await screen.bump(user_id=1, kind="del_confirm")
    assert old_v != new_v
    assert await screen.check(1, "del_confirm", old_v) is False
    assert await screen.check(1, "del_confirm", new_v) is True


async def test_screen_version_check_returns_false_when_no_version_stored(screen):
    """User never opened that screen → any callback's v is stale."""
    assert await screen.check(1, "del_confirm", "anything") is False


async def test_screen_version_is_compact_for_callback_budget(screen):
    """The token must be short enough to live inside the 64-byte callback budget
    alongside other CategoryCB fields."""
    v = await screen.bump(user_id=1, kind="cat_pick")
    # 3 bytes urlsafe = 4 chars.
    assert len(v) <= 8

    payload = CategoryCB(
        action="pick",
        category_id=2_147_483_647,
        flow="add",
        v=v,
    ).pack()
    assert len(payload.encode("utf-8")) <= TELEGRAM_CALLBACK_LIMIT


async def test_screen_versions_are_per_user(screen):
    v1 = await screen.bump(user_id=1, kind="cat_pick")
    v2 = await screen.bump(user_id=2, kind="cat_pick")
    # User 1's token is still valid for user 1 even after user 2 bumped theirs.
    assert await screen.check(1, "cat_pick", v1) is True
    assert await screen.check(2, "cat_pick", v2) is True
    # Cross-user use is rejected.
    assert await screen.check(1, "cat_pick", v2) is False


async def test_screen_versions_are_per_kind(screen):
    v_del = await screen.bump(user_id=1, kind="del_confirm")
    v_cat = await screen.bump(user_id=1, kind="cat_pick")
    assert await screen.check(1, "del_confirm", v_del) is True
    assert await screen.check(1, "del_confirm", v_cat) is False
