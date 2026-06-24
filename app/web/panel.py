"""Subadmin panel routes. All data is scoped to the logged-in user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_subadmin
from app.db.base import get_db
from app.db.models import Plan, User
from app.services import admin as admin_svc
from app.services import content as content_svc
from app.services import payments as pay_svc
from app.services import subscription as sub_svc
from app.web.templates_env import templates

router = APIRouter(prefix="/panel", tags=["panel"])


@router.get("", response_class=HTMLResponse)
async def panel_home(
    request: Request,
    user: User = Depends(require_subadmin),
    db: AsyncSession = Depends(get_db),
):
    roots = await content_svc.list_user_contents(db, user.id, None)
    total = await content_svc.count_user_videos(db, user.id)
    eff = await sub_svc.get_effective_plan(db, user)
    return templates.TemplateResponse(
        "panel/home.html",
        {
            "request": request,
            "user": user,
            "roots": roots,
            "total_videos": total,
            "eff": eff,
        },
    )


@router.get("/content/{content_id}", response_class=HTMLResponse)
async def panel_content(
    content_id: int,
    request: Request,
    user: User = Depends(require_subadmin),
    db: AsyncSession = Depends(get_db),
):
    content = await content_svc.get_owned_content(db, user.id, content_id)
    if content is None:
        return RedirectResponse(url="/panel", status_code=303)
    children = await content_svc.list_user_contents(db, user.id, content_id)
    return templates.TemplateResponse(
        "panel/content.html",
        {
            "request": request,
            "user": user,
            "content": content,
            "children": children,
            "sources": content.sources,
        },
    )


@router.get("/plans", response_class=HTMLResponse)
async def panel_plans(
    request: Request,
    user: User = Depends(require_subadmin),
    db: AsyncSession = Depends(get_db),
):
    plans = await admin_svc.list_plans(db, active_only=True)
    methods = await admin_svc.list_payment_methods(db, active_only=True)
    my_requests = await pay_svc.list_user_requests(db, user.id)
    eff = await sub_svc.get_effective_plan(db, user)
    return templates.TemplateResponse(
        "panel/plans.html",
        {
            "request": request,
            "user": user,
            "plans": plans,
            "methods": methods,
            "requests": my_requests,
            "eff": eff,
        },
    )


@router.post("/plans/buy")
async def panel_buy(
    plan_id: int = Form(...),
    method_id: str = Form(""),
    amount: int = Form(0),
    transaction_ref: str = Form(""),
    user: User = Depends(require_subadmin),
    db: AsyncSession = Depends(get_db),
):
    await pay_svc.create_request(
        db,
        user_id=user.id,
        plan_id=plan_id,
        method_id=int(method_id) if method_id else None,
        amount=amount,
        transaction_ref=transaction_ref or None,
    )
    return RedirectResponse(url="/panel/plans", status_code=303)
