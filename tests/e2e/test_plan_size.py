"""Plan size against a real database: it never shrinks, grows one step per
week of on-time closes, and an open plan can be enlarged in place."""
from __future__ import annotations

import json
from datetime import timedelta

from app.domain import day_plan as plan_rules
from app.services import push_service as ps
from app.services.day_plan_service import DayPlanService
from tests.e2e.harness import UID


async def _history(h, rows: list[tuple[int, int]]) -> None:
    """Closed plans, oldest first: (size, days late)."""
    await h.sql("delete from day_plans where user_id=:u", u=UID)
    today = await h.today()
    for back, (size, late) in enumerate(reversed(rows), start=1):
        opened = today - timedelta(days=back * 5)
        await h.sql(
            "insert into day_plans (user_id, track, size, items, opened_on, closed_at)"
            " values (:u, 'en', :n, '[]'::jsonb, :d, (cast(:d as date) + cast(:late as int)) + time '12:00')",
            u=UID, n=size, d=opened, late=late,
        )


async def _next_size(h) -> int:
    from app.infrastructure.repositories.users import UserRepository

    async with h.sm() as session:
        user = await UserRepository(session).get(UID)
        return await DayPlanService(session)._next_size(user, ps._TRACK)


async def test_late_plans_never_shrink_it_and_a_small_one_comes_back_to_default(h):
    await _history(h, [(16, 3)] * 5)
    assert await _next_size(h) == plan_rules.DEFAULT_SIZE


async def test_a_week_on_time_grows_it_once_not_every_day_after(h):
    await _history(h, [(30, 0)] * 7)
    assert await _next_size(h) == 32
    # The day after growing: one plan at 32, so no second step yet.
    await _history(h, [(30, 0)] * 7 + [(32, 0)])
    assert await _next_size(h) == 32


async def test_an_open_plan_grows_in_place_keeping_done_slots(h):
    from app.infrastructure.repositories.users import UserRepository

    await h.fresh_day(["repeat"] * 6 + ["grammar"] * 4 + ["new_theme_word", "new_word", "new_word", "phrase", "phrase"])
    items = await h.plan()
    items[0]["done"] = True
    await h.sql(
        "update day_plans set items=cast(:i as jsonb), size=16 where user_id=:u and closed_at is null",
        u=UID, i=json.dumps(items),
    )
    async with h.sm() as session:
        user = await UserRepository(session).get(UID)
        svc = DayPlanService(session)
        plan = await svc.open_plan_or_none(UID, ps._TRACK)
        added = await svc.grow_open_plan(user, ps._TRACK, plan, 30)
        await session.commit()
    after = await h.plan()
    (size,), = await h.sql("select size from day_plans where user_id=:u and closed_at is null", u=UID)
    assert size == 30
    assert len(after) == 15 + added
    assert added > 0
    assert after[0]["done"] is True
    assert sum(1 for i in after if i["kind"] == "grammar") == 4
