"""Authentication helpers: credential check + session token issuance."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token, verify_password
from app.db.models import User


async def authenticate(
    db: AsyncSession, username: str, password: str
) -> User | None:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_session(user: User) -> str:
    return create_token({"uid": user.id, "role": user.role.value})
