"""Admin-side service logic: users, plans, payment methods, subscriptions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import (
    AuditLog,
    Content,
    PaymentMethod,
    Plan,
    User,
    UserRole,
    VideoSource,
)


async def list_users(db: AsyncSession) -> list[User]:
    rows = await db.scalars(select(User).order_by(User.created_at.desc()))
    return list(rows)


async def list_plans(db: AsyncSession, active_only: bool = False) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.price.asc())
    if active_only:
        stmt = stmt.where(Plan.is_active.is_(True))
    rows = await db.scalars(stmt)
    return list(rows)


async def list_payment_methods(
    db: AsyncSession, active_only: bool = False
) -> list[PaymentMethod]:
    stmt = select(PaymentMethod).order_by(PaymentMethod.name.asc())
    if active_only:
        stmt = stmt.where(PaymentMethod.is_active.is_(True))
    rows = await db.scalars(stmt)
    return list(rows)


async def create_subadmin(
    db: AsyncSession, username: str, password: str
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole.subadmin,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def set_user_active(db: AsyncSession, user_id: int, active: bool) -> None:
    user = await db.get(User, user_id)
    if user:
        user.is_active = active


async def assign_plan(
    db: AsyncSession, user_id: int, plan_id: int | None, extend_days: int | None
) -> None:
    user = await db.get(User, user_id)
    if not user:
        return
    if plan_id is None:
        user.plan_id = None
        user.plan_expires_at = None
        return
    plan = await db.get(Plan, plan_id)
    if not plan:
        return
    user.plan_id = plan.id
    days = extend_days if extend_days is not None else plan.duration_days
    base = user.plan_expires_at
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = base if (base and base > now) else now
    user.plan_expires_at = start + timedelta(days=days)


async def create_plan(db: AsyncSession, **kwargs) -> Plan:
    plan = Plan(**kwargs)
    db.add(plan)
    await db.flush()
    return plan


async def create_payment_method(db: AsyncSession, **kwargs) -> PaymentMethod:
    method = PaymentMethod(**kwargs)
    db.add(method)
    await db.flush()
    return method


async def toggle_payment_method(db: AsyncSession, method_id: int) -> None:
    method = await db.get(PaymentMethod, method_id)
    if method:
        method.is_active = not method.is_active


async def dashboard_stats(db: AsyncSession) -> dict:
    users = await db.scalar(select(func.count(User.id)))
    subadmins = await db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.subadmin)
    )
    contents = await db.scalar(select(func.count(Content.id)))
    videos = await db.scalar(select(func.count(VideoSource.id)))
    return {
        "users": users or 0,
        "subadmins": subadmins or 0,
        "contents": contents or 0,
        "videos": videos or 0,
    }


async def recent_logs(db: AsyncSession, limit: int = 50) -> list[AuditLog]:
    rows = await db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    return list(rows)


async def log_action(
    db: AsyncSession, actor_id: int | None, action: str, detail: str | None = None
) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, detail=detail))
