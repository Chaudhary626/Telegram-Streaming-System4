"""Shared Pyrogram client manager for MTProto streaming.

A single long-lived Pyrogram session is used for all streaming requests. This
avoids re-authenticating per request and lets Pyrogram reuse its DC connection
pool. The client runs as a *bot* session (BOT_TOKEN) which is sufficient to read
messages from channels where the bot is an administrator.

The session file is stored under ./sessions so it survives restarts (mounted as
a volume in docker-compose).
"""
from __future__ import annotations

import asyncio
import os

from pyrogram import Client

from app.config import get_settings

settings = get_settings()

_SESSION_DIR = "sessions"
os.makedirs(_SESSION_DIR, exist_ok=True)


class TelegramStreamClient:
    """Lazily-started singleton wrapper around a Pyrogram bot client."""

    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def start(self) -> Client:
        async with self._lock:
            if self._client is None:
                self._client = Client(
                    name="stream_bot",
                    api_id=settings.API_ID,
                    api_hash=settings.API_HASH,
                    bot_token=settings.BOT_TOKEN,
                    workdir=_SESSION_DIR,
                    # More workers => more parallel get_file calls under load.
                    workers=8,
                    no_updates=True,
                    sleep_threshold=30,
                )
            if not self._client.is_connected:
                await self._client.start()
            return self._client

    async def stop(self) -> None:
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                await self._client.stop()

    def get(self) -> Client:
        if self._client is None or not self._client.is_connected:
            raise RuntimeError("Telegram client not started")
        return self._client


# Module-level singleton shared by the streaming layer.
tg_client = TelegramStreamClient()
