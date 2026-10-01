"""Pack admin: ownership, the autofill trap, and what editing cannot break.

Two things make this risky rather than routine.

The first is ownership. Packs were edited only by migrations until now, and the
admin edits the same rows — whichever ran last would win silently. `origin`
splits that, which means a migration can now ship a fix that never arrives, so
the skip must be loud.

The second is the trap migration 0058 had to clean up after: `pack_top_up` reads
only «Темы» and «Фразы», so moving a pack elsewhere stops it being delivered
with nothing on screen saying so.
"""
from __future__ import annotations

import pytest

from app.services.pack_admin_service import (
    AUTOFILL_CATEGORIES,
    KNOWN_CATEGORIES,
    ORIGIN_ADMIN,
    PackAdminService,
    category_at,
    index_of,
)


class _Pack:
    def __init__(self, pid=1, title="Еда", category="Темы", position=3, active=True, origin="migration"):
        self.id = pid
        self.title = title
        self.category = category
        self.position = position
        self.is_active = active
        self.origin = origin


class _Session:
    def __init__(self):
        self.flushes = 0

    async def flush(self):
        self.flushes += 1


def _service(packs=None):
    service = PackAdminService.__new__(PackAdminService)
    service._session = _Session()
    if packs is not None:
        async def packs_in(category):
            return [p for p in packs if p.category == category]
        service.packs_in = packs_in
    return service


@pytest.mark.asyncio
async def test_toggling_claims_the_pack_for_the_admin():
    """Every write moves ownership. A pack cannot be half-owned: if migrations
    still thought this one was theirs, the next deploy would undo the change
    with nothing in the log."""
    pack = _Pack()
    await _service().toggle_active(pack)
    assert pack.origin == ORIGIN_ADMIN


@pytest.mark.asyncio
async def test_renaming_claims_the_pack_too():
    pack = _Pack()
    await _service().rename(pack, "Еда и напитки")
    assert pack.title == "Еда и напитки"
    assert pack.origin == ORIGIN_ADMIN


@pytest.mark.asyncio
async def test_a_long_title_is_cut_to_the_column():
    """`packs.title` is String(128). A longer title would raise on flush and the
    admin would see a crash instead of a result."""
    pack = _Pack()
    await _service().rename(pack, "д" * 400)
    assert len(pack.title) <= 128


@pytest.mark.asyncio
async def test_moving_swaps_with_the_neighbour_rather_than_renumbering():
    """Positions decide the order the top-up walks. Rewriting a category's
    numbers to move one pack is how a position drifts from what anybody chose."""
    a, b, c = _Pack(1, "A", position=0), _Pack(2, "B", position=1), _Pack(3, "C", position=2)
    service = _service([a, b, c])
    assert await service.move(b, -1) is True
    assert (a.position, b.position) == (1, 0)
    assert c.position == 2, "сосед через одного не должен двигаться"


@pytest.mark.asyncio
async def test_moving_past_the_edge_changes_nothing():
    a, b = _Pack(1, "A", position=0), _Pack(2, "B", position=1)
    service = _service([a, b])
    assert await service.move(a, -1) is False
    assert (a.position, b.position) == (0, 1)
    assert a.origin == "migration", "неудавшийся сдвиг не должен менять владельца"


def test_leaving_the_autofill_categories_is_flagged():
    """The 0058 trap: a pack moved out of «Темы»/«Фразы» keeps existing and
    stops being handed out. The screen has to say so at the moment it happens."""
    assert PackAdminService.leaves_autofill("Темы", "Узкие темы") is True
    assert PackAdminService.leaves_autofill("Фразы", "Экзамены") is True
    assert PackAdminService.leaves_autofill("Темы", "Фразы") is False
    assert PackAdminService.leaves_autofill("Уровни", "Экзамены") is False


def test_the_autofill_categories_match_what_the_top_up_reads():
    """If `_top_up` ever walks a third category, this list has to learn about it
    — otherwise the warning lies in the direction that loses words."""
    import inspect

    from app.services.day_plan_service import DayPlanService

    src = inspect.getsource(DayPlanService._top_up)
    for category in AUTOFILL_CATEGORIES:
        assert f'"{category}"' in src, category


def test_category_indexes_are_stable_and_complete():
    """Callbacks carry the index, so a stale button in somebody's chat resolves
    against this list. Append only — reordering moves packs to wrong places."""
    assert KNOWN_CATEGORIES[0] == "Темы"
    assert KNOWN_CATEGORIES[1] == "Фразы"
    for i, name in enumerate(KNOWN_CATEGORIES):
        assert category_at(i) == name
        assert index_of(name) == i
    assert category_at(len(KNOWN_CATEGORIES)) is None
    assert category_at(-1) is None
    assert index_of("Выдуманная") == -1


def test_the_callback_fits_telegram_budget():
    """64 bytes, and Cyrillic costs two per character — the reason categories
    travel as an index."""
    from app.bot.callbacks.schema import PackAdminCB

    worst = PackAdminCB(action="cat_set", cat=len(KNOWN_CATEGORIES) - 1, pack_id=999_999_999)
    assert len(worst.pack().encode()) <= 64


@pytest.mark.asyncio
async def test_handing_a_pack_back_does_not_claim_it():
    """The escape hatch for the failure this design allows. If it claimed the
    pack on the way out it would do nothing at all."""
    pack = _Pack(origin=ORIGIN_ADMIN)
    await _service().reset_to_migration(pack)
    assert pack.origin == "migration"


# ---- migrations must not skip silently ------------------------------------- #


class _Bind:
    """Stands in for the alembic connection."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, _stmt, _params=None):
        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _Result(self.rows)


def test_a_migration_may_edit_packs_it_still_owns():
    from migrations.pack_ownership import editable_slugs

    bind = _Bind([("colors", "migration"), ("food", "admin")])
    mine, theirs = editable_slugs(bind, ["colors", "food"])
    assert mine == ["colors"]
    assert theirs == ["food"]


def test_a_slug_that_does_not_exist_yet_is_editable():
    """Creating a pack is not a conflict with anybody."""
    from migrations.pack_ownership import editable_slugs

    mine, theirs = editable_slugs(_Bind([]), ["brand_new"])
    assert mine == ["brand_new"]
    assert theirs == []


def test_the_skip_is_printed_not_swallowed(capsys):
    """The whole reason `origin` is safe to have. A migration that ships a fix
    for a hand-edited pack will skip it — and a deploy reporting success while
    the fix never arrived is how data quietly diverges for a month."""
    from migrations.pack_ownership import report_skipped

    report_skipped(["food", "colors"])
    out = capsys.readouterr().out
    assert "food" in out and "colors" in out
    assert "НЕ применены" in out


def test_nothing_is_printed_when_nothing_was_skipped(capsys):
    """Noise in a deploy log trains people to ignore it."""
    from migrations.pack_ownership import report_skipped

    report_skipped([])
    assert capsys.readouterr().out == ""
