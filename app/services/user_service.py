from __future__ import annotations

from app.domain.models import User


class UserService:
    """Global user-level helpers. Per-track settings live in UserTrackService."""

    MIN_GOAL = 1
    MAX_GOAL = 100

    @classmethod
    def is_valid_goal(cls, value: int) -> bool:
        return cls.MIN_GOAL <= value <= cls.MAX_GOAL

    @staticmethod
    async def complete_onboarding(user: User) -> None:
        user.onboarding_completed = True
