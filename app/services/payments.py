"""Payment request workflow (manual verification by admin)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import PaymentRequest, PaymentStatus, Plan, User
from app.services.admin import assign_plan


async def create_request(
    db: AsyncSession,
    *,
    user_id: int,
    plan_id: int,
    method_id: int | None,
    amount: int,
    transaction_ref: str | None,
    proof_file_id: str | None = None,
) -> PaymentRequest:
    req = PaymentRequest(
        user_id=user_id,
        plan_id=plan_id,
        method_id=method_id,
        amount=amount,
        transaction_ref=transaction_ref,
        proof_file_id=proof_file_id,
        status=PaymentStatus.pending,
    )
    db.add(req)
    await db.flush()
    return req


async def list_requests(
    db: AsyncSession, status: PaymentStatus | None = None
) -> list[PaymentRequest]:
    stmt = (
        select(PaymentRequest)
        .options(selectinload(PaymentRequest.user))
        .order_by(PaymentRequest.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(PaymentRequest.status == status)
    rows = await db.scalars(stmt)
    return list(rows)


async def list_user_requests(
    db: AsyncSession, user_id: int
) -> list[PaymentRequest]:
    rows = await db.scalars(
        select(PaymentRequest)
        .where(PaymentRequest.user_id == user_id)
        .order_by(PaymentRequest.created_at.desc())
    )
    return list(rows)


async def approve_request(
    db: AsyncSession, request_id: int, note: str | None = None
) -> bool:
    req = await db.get(PaymentRequest, request_id)
    if req is None or req.status != PaymentStatus.pending:
        return False
    req.status = PaymentStatus.approved
    req.admin_note = note
    req.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    # Activate the plan for the user.
    await assign_plan(db, req.user_id, req.plan_id, extend_days=None)
    return True


async def reject_request(
    db: AsyncSession, request_id: int, note: str | None = None
) -> bool:
    req = await db.get(PaymentRequest, request_id)
    if req is None or req.status != PaymentStatus.pending:
        return False
    req.status = PaymentStatus.rejected
    req.admin_note = note
    req.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return True
