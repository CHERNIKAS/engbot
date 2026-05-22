from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def create(self, telegram_id: int, language: str = "ru") -> User:
        user = User(telegram_id=telegram_id, language=language)
        self.session.add(user)
        await self.session.flush()
        return user

    async def upsert_by_telegram_id(self, telegram_id: int, language: str = "ru") -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            return user, False
        # Race-safe: two concurrent first updates from the same user (e.g. a
        # double-tapped /start) must not blow up on the unique telegram_id index.
        # ON CONFLICT DO NOTHING + reselect resolves the race without a 500.
        await self.session.execute(
            pg_insert(User)
            .values(telegram_id=telegram_id, language=language)
            .on_conflict_do_nothing(index_elements=["telegram_id"])
        )
        await self.session.flush()
        user = await self.get_by_telegram_id(telegram_id)
        return user, True  # type: ignore[return-value]

    async def list_for_reminders(self) -> list[User]:
        """Authorized, onboarded users — candidates for daily reminders."""
        result = await self.session.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.is_authorized.is_(True),
            )
        )
        return list(result.scalars().all())

    async def list_for_push(self) -> list[User]:
        """Onboarded users — targets for push-learning (the always-on main mode).

        Deliberately does NOT require is_authorized: that flag is only set by the
        password gate, so coupling push to it means push silently sends nothing
        whenever ACCESS_PASSWORD is empty. When the gate IS on, unauthorized
        users can't reach onboarding anyway, so onboarding_completed is the right
        and sufficient filter in both cases."""
        result = await self.session.execute(
            select(User).where(User.onboarding_completed.is_(True))
        )
        return list(result.scalars().all())
