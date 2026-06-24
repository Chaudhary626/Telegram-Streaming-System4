"""FastAPI application entrypoint.

Phase 2 adds the MTProto stream server: a managed Pyrogram client is started on
application startup and stopped on shutdown, and the streaming routes are
registered. Phase 1's health check and DB initialization remain.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.stream import router as stream_router
from app.bot.client import bot_client
from app.config import get_settings
from app.db.init_db import init as init_db
from app.telegram.client import tg_client
from app.web.admin import router as admin_router
from app.web.auth import router as auth_router
from app.web.panel import router as panel_router
from app.web.player import router as player_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Start the shared MTProto streaming client and the update-handling bot.
    await tg_client.start()
    await bot_client.start()
    try:
        yield
    finally:
        await bot_client.stop()
        await tg_client.stop()


app = FastAPI(
    title="Telegram Video Streaming System",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "web", "static")),
    name="static",
)

app.include_router(stream_router)
app.include_router(auth_router)
app.include_router(panel_router)
app.include_router(player_router)
app.include_router(admin_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {
        "status": "ok",
        "env": settings.ENV,
        "telegram_connected": tg_client.started,
        "bot_connected": bot_client.started,
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    return {
        "name": "Telegram Video Streaming System",
        "version": app.version,
        "phase": 5,
    }
