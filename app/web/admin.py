"""Admin panel routes, mounted behind a secret URL path.

Security model (defense in depth):
  1. The router prefix includes a secret path segment (ADMIN_SECRET_PATH), so
     the panel is not at a guessable/public URL.
  2. Every route additionally requires an authenticated *admin* session
     (require_admin), so knowing the path alone is never sufficient.

The secret segment is validated on every request via `_check_secret`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import require_admin
from app.db.base import get_db
from app.db.models import PaymentStatus, User
from app.services import admin as admin_svc
from app.services import password as pwd_svc
from app.services import payments as pay_svc
from app.web.templates_env import templates

settings = get_settings()
router = APIRouter(prefix="/admin/{secret}", tags=["admin"])


def _check_secret(secret: str) -> None:
    if secret != settings.ADMIN_SECRET_PATH:
        # Return 404 (not 403) so the path's existence is not revealed.
        raise HTTPException(status_code=404, detail="Not found")


def _base() -> str:
    return f"/admin/{settings.ADMIN_SECRET_PATH}"


@router.get("", response_class=HTMLResponse)
async def dashboard(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    stats = await admin_svc.dashboard_stats(db)
    pending = await pay_svc.list_requests(db, PaymentStatus.pending)
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "admin": admin,
            "base": _base(),
            "stats": stats,
            "pending_count": len(pending),
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    users = await admin_svc.list_users(db)
    plans = await admin_svc.list_plans(db)
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "admin": admin,
            "base": _base(),
            "users": users,
            "plans": plans,
        },
    )


@router.post("/users/create")
async def users_create(
    secret: str,
    username: str = Form(...),
    password: str = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    await admin_svc.create_subadmin(db, username, password)
    await admin_svc.log_action(db, admin.id, "create_subadmin", username)
    return RedirectResponse(url=f"{_base()}/users", status_code=303)


@router.post("/users/{user_id}/active")
async def users_active(
    secret: str,
    user_id: int,
    active: int = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    await admin_svc.set_user_active(db, user_id, bool(active))
    await admin_svc.log_action(db, admin.id, "set_active", f"{user_id}={active}")
    return RedirectResponse(url=f"{_base()}/users", status_code=303)


@router.post("/users/{user_id}/plan")
async def users_plan(
    secret: str,
    user_id: int,
    plan_id: str = Form(""),
    extend_days: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    pid = int(plan_id) if plan_id else None
    days = int(extend_days) if extend_days else None
    await admin_svc.assign_plan(db, user_id, pid, days)
    await admin_svc.log_action(db, admin.id, "assign_plan", f"u{user_id}->p{pid}")
    return RedirectResponse(url=f"{_base()}/users", status_code=303)


@router.post("/users/{user_id}/password")
async def users_set_password(
    secret: str,
    user_id: int,
    password: str = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    try:
        await pwd_svc.set_password_by_user_id(db, user_id, password)
        await admin_svc.log_action(db, admin.id, "set_password", f"u{user_id}")
    except pwd_svc.PasswordError:
        pass
    return RedirectResponse(url=f"{_base()}/users", status_code=303)


@router.get("/plans", response_class=HTMLResponse)
async def plans_page(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    plans = await admin_svc.list_plans(db)
    return templates.TemplateResponse(
        "admin/plans.html",
        {"request": request, "admin": admin, "base": _base(), "plans": plans},
    )


@router.post("/plans/create")
async def plans_create(
    secret: str,
    name: str = Form(...),
    price: int = Form(0),
    duration_days: int = Form(30),
    max_videos: int = Form(0),
    features: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    await admin_svc.create_plan(
        db,
        name=name,
        price=price,
        duration_days=duration_days,
        max_videos=max_videos,
        features=features or None,
    )
    await admin_svc.log_action(db, admin.id, "create_plan", name)
    return RedirectResponse(url=f"{_base()}/plans", status_code=303)


@router.get("/methods", response_class=HTMLResponse)
async def methods_page(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    methods = await admin_svc.list_payment_methods(db)
    return templates.TemplateResponse(
        "admin/methods.html",
        {"request": request, "admin": admin, "base": _base(), "methods": methods},
    )


@router.post("/methods/create")
async def methods_create(
    secret: str,
    name: str = Form(...),
    type: str = Form(...),
    details: str = Form(""),
    instructions: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    await admin_svc.create_payment_method(
        db,
        name=name,
        type=type,
        details=details or None,
        instructions=instructions or None,
    )
    await admin_svc.log_action(db, admin.id, "create_method", name)
    return RedirectResponse(url=f"{_base()}/methods", status_code=303)


@router.post("/methods/{method_id}/toggle")
async def methods_toggle(
    secret: str,
    method_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    await admin_svc.toggle_payment_method(db, method_id)
    return RedirectResponse(url=f"{_base()}/methods", status_code=303)


@router.get("/payments", response_class=HTMLResponse)
async def payments_page(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    pending = await pay_svc.list_requests(db, PaymentStatus.pending)
    history = await pay_svc.list_requests(db)
    return templates.TemplateResponse(
        "admin/payments.html",
        {
            "request": request,
            "admin": admin,
            "base": _base(),
            "pending": pending,
            "history": history,
        },
    )


@router.post("/payments/{request_id}/approve")
async def payments_approve(
    secret: str,
    request_id: int,
    note: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    ok = await pay_svc.approve_request(db, request_id, note or None)
    await admin_svc.log_action(
        db, admin.id, "approve_payment", f"req{request_id} ok={ok}"
    )
    return RedirectResponse(url=f"{_base()}/payments", status_code=303)


@router.post("/payments/{request_id}/reject")
async def payments_reject(
    secret: str,
    request_id: int,
    note: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    ok = await pay_svc.reject_request(db, request_id, note or None)
    await admin_svc.log_action(
        db, admin.id, "reject_payment", f"req{request_id} ok={ok}"
    )
    return RedirectResponse(url=f"{_base()}/payments", status_code=303)


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    secret: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_secret(secret)
    logs = await admin_svc.recent_logs(db)
    return templates.TemplateResponse(
        "admin/logs.html",
        {"request": request, "admin": admin, "base": _base(), "logs": logs},
    )
