"""Set/reset a user's panel password (used by bot and admin panel)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import User

MIN_LEN = 6


class PasswordError(ValueError):
    pass


def _validate(password: str) -> None:
    if len(password) < MIN_LEN:
        raise PasswordError(
            f"Password must be at least {MIN_LEN} characters."
        )


async def set_password_by_user_id(
    db: AsyncSession, user_id: int, password: str
) -> bool:
    _validate(password)
    user = await db.get(User, user_id)
    if user is None:
        return False
    user.password_hash = hash_password(password)
    return True


async def set_password_by_tg(
    db: AsyncSession, telegram_id: int, password: str
) -> bool:
    _validate(password)
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        return False
    user.password_hash = hash_password(password)
    return True
