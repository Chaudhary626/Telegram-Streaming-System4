"""Bot Pyrogram client (handles updates), separate from the streaming client."""
from __future__ import annotations

import asyncio
import os

from pyrogram import Client

from app.config import get_settings

settings = get_settings()

_SESSION_DIR = "sessions"
os.makedirs(_SESSION_DIR, exist_ok=True)


class BotClient:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        return self._client is not None and self._client.is_connected

    def get(self) -> Client:
        if self._client is None:
            raise RuntimeError("Bot client not initialized")
        return self._client

    async def start(self) -> Client:
        async with self._lock:
            if self._client is None:
                self._client = Client(
                    name="content_bot",
                    api_id=settings.API_ID,
                    api_hash=settings.API_HASH,
                    bot_token=settings.BOT_TOKEN,
                    workdir=_SESSION_DIR,
                    workers=8,
                )
                # Register handlers once the client object exists.
                from app.bot.handlers import register_handlers

                register_handlers(self._client)
            if not self._client.is_connected:
                await self._client.start()
            return self._client

    async def stop(self) -> None:
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                await self._client.stop()


bot_client = BotClient()
