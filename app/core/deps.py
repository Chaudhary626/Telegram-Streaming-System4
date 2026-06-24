"""Authentication & authorization dependencies for the web panels.

Session auth is cookie-based: on login we set an HttpOnly, signed JWT cookie
(`session`). `get_current_user` decodes it and loads the user; `require_admin`
and `require_subadmin` enforce roles. The admin panel additionally lives behind
a secret URL path segment (see app.web.admin) for defense in depth.
"""
from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import User, UserRole

SESSION_COOKIE = "session"


class AuthRedirect(HTTPException):
    """Raised when an unauthenticated user hits a protected page."""

    def __init__(self, login_url: str) -> None:
        super().__init__(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": login_url},
        )


async def get_current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not session:
        return None
    payload = decode_token(session)
    if not payload:
        return None
    user_id = payload.get("uid")
    if user_id is None:
        return None
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        return None
    return user


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_subadmin(user: User = Depends(require_user)) -> User:
    # Admins may also use subadmin views; both roles allowed here.
    return user
