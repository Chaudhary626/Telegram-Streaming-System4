"""Authentication routes shared by both panels (login / logout)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SESSION_COOKIE
from app.config import get_settings
from app.db.base import get_db
from app.db.models import UserRole
from app.services.auth import authenticate, issue_session
from app.web.templates_env import templates

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str = "/panel"):
    return templates.TemplateResponse(
        "login.html", {"request": request, "next": next, "error": None}
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/panel"),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate(db, username, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "next": next, "error": "Invalid credentials"},
            status_code=401,
        )
    # Admins land on the secret admin path; subadmins on the panel.
    if user.role == UserRole.admin and next in ("/panel", ""):
        next = f"/admin/{settings.ADMIN_SECRET_PATH}"
    token = issue_session(user)
    resp = RedirectResponse(url=next, status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=60 * 60 * 24,
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
