"""Enlarge every open day plan to the default size (one-off, 2026-11-16).

Plans opened before the shrink rule was removed keep the size they were opened
with until they close; this tops them up in place so today is already 30.
Done slots stay done. Prints what it would do; `--apply` writes.

    docker compose -f docker-compose.prod.yml exec -T bot python scripts/grow_open_plans.py [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.domain import day_plan as plan_rules  # noqa: E402
from app.domain.enums import LearningTrack  # noqa: E402
from app.domain.models import DayPlan, User  # noqa: E402
from app.services.day_plan_service import DayPlanService  # noqa: E402


async def main(apply: bool) -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        plans = (
            await session.execute(
                select(DayPlan).where(
                    DayPlan.closed_at.is_(None), DayPlan.size < plan_rules.DEFAULT_SIZE
                )
            )
        ).scalars().all()
        for plan in plans:
            user = await session.get(User, plan.user_id)
            before = len(plan.items or [])
            added = await DayPlanService(session).grow_open_plan(
                user, LearningTrack(plan.track), plan, plan_rules.DEFAULT_SIZE
            )
            print(f"uid {plan.user_id} plan {plan.id}: {before} → {before + added} slots")
        if apply:
            await session.commit()
            print("applied")
        else:
            await session.rollback()
            print("dry run — nothing written (--apply to write)")
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    asyncio.run(main(ap.parse_args().apply))
