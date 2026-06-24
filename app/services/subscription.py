"""Subscription enforcement: effective plan, expiry handling, upload limits.

This module is the single source of truth for what a user is *currently*
allowed to do. Expiry is handled by downgrading: if a user's `plan_expires_at`
is in the past (or they have no plan), they are treated as the **Free** plan
regardless of the stored `plan_id`. Premium features and video limits are then
derived from this *effective* plan everywhere (bot upload flow + panel).

Video limits use `Plan.max_videos`, where `0` means unlimited.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.content import count_user_videos
from app.db.models import Plan, User

FREE_PLAN_NAME = "Free"


@dataclass
class EffectivePlan:
    name: str
    max_videos: int  # 0 == unlimited
    features: str | None
    is_expired: bool
    expires_at: datetime | None

    @property
    def unlimited(self) -> bool:
        return self.max_videos == 0


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _free_plan(db: AsyncSession) -> Plan | None:
    return await db.scalar(select(Plan).where(Plan.name == FREE_PLAN_NAME))


async def get_effective_plan(db: AsyncSession, user: User) -> EffectivePlan:
    """Resolve the plan a user is *currently* entitled to.

    Downgrades expired or plan-less users to Free.
    """
    expired = False
    plan: Plan | None = None

    if user.plan_id is not None:
        plan = await db.get(Plan, user.plan_id)
        if user.plan_expires_at is not None and user.plan_expires_at < _now():
            expired = True
            plan = None  # fall through to Free below

    if plan is None:
        plan = await _free_plan(db)

    if plan is None:
        # No Free plan seeded; safest default is a tiny allowance.
        return EffectivePlan(
            name=FREE_PLAN_NAME,
            max_videos=5,
            features="Basic playback",
            is_expired=expired,
            expires_at=user.plan_expires_at,
        )

    return EffectivePlan(
        name=plan.name,
        max_videos=plan.max_videos,
        features=plan.features,
        is_expired=expired,
        expires_at=user.plan_expires_at,
    )


@dataclass
class UploadCheck:
    allowed: bool
    used: int
    limit: int  # 0 == unlimited
    plan_name: str
    reason: str | None = None


async def can_upload(db: AsyncSession, user: User) -> UploadCheck:
    """Return whether the user may add one more video under their plan."""
    eff = await get_effective_plan(db, user)
    used = await count_user_videos(db, user.id)
    if eff.unlimited:
        return UploadCheck(
            allowed=True, used=used, limit=0, plan_name=eff.name
        )
    if used >= eff.max_videos:
        reason = (
            f"You've reached your **{eff.name}** plan limit of "
            f"{eff.max_videos} videos."
        )
        if eff.is_expired:
            reason = (
                "Your subscription has expired, so you're on the **Free** plan "
                f"(limit {eff.max_videos} videos)."
            )
        return UploadCheck(
            allowed=False,
            used=used,
            limit=eff.max_videos,
            plan_name=eff.name,
            reason=reason,
        )
    return UploadCheck(
        allowed=True, used=used, limit=eff.max_videos, plan_name=eff.name
    )


def has_feature(eff: EffectivePlan, keyword: str) -> bool:
    """Lightweight feature gate by keyword match in the plan's features text."""
    if eff.features is None:
        return False
    return keyword.lower() in eff.features.lower()
