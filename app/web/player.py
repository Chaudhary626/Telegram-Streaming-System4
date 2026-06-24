"""Public player routes: /watch/{slug} and /embed/{slug}.

These are intentionally public (no auth) so videos can be embedded on external
sites. Access to the underlying bytes is still gated by signed, expiring stream
tokens minted per source in the player payload.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.player import build_player_payload
from app.web.templates_env import templates

router = APIRouter(tags=["player"])


@router.get("/watch/{slug}", response_class=HTMLResponse)
async def watch(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await build_player_payload(db, slug)
    if payload is None:
        return templates.TemplateResponse(
            "player/notfound.html", {"request": request, "slug": slug},
            status_code=404,
        )
    return templates.TemplateResponse(
        "player/watch.html",
        {"request": request, "data": payload, "embed": False},
    )


@router.get("/embed/{slug}", response_class=HTMLResponse)
async def embed(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    payload = await build_player_payload(db, slug)
    if payload is None:
        return templates.TemplateResponse(
            "player/notfound.html", {"request": request, "slug": slug},
            status_code=404,
        )
    return templates.TemplateResponse(
        "player/watch.html",
        {"request": request, "data": payload, "embed": True},
    )
