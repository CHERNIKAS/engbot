from __future__ import annotations

from sqlalchemy import select
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
        return await self.create(telegram_id=telegram_id, language=language), True

    async def list_for_reminders(self) -> list[User]:
        """Authorized, onboarded users — candidates for daily reminders."""
        result = await self.session.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.is_authorized.is_(True),
            )
        )
        return list(result.scalars().all())
