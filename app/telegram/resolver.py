"""Resolve a VideoSource into a usable, current Telegram file_id.

Telegram `file_id`s are generally stable for a given bot, but they can become
invalid (e.g. after long periods or DC migration). To stay robust we resolve a
stored source against the original message: we re-fetch the message by
`channel_id` + `message_id` and read the current `file_id` from it. The stored
`file_id` is used as a fast path / fallback.

Resolved file_ids are cached in-process keyed by source id for a short TTL to
avoid a Telegram round-trip on every range request of the same playback.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from pyrogram import Client

_CACHE_TTL = 600  # seconds


@dataclass
class ResolvedFile:
    file_id: str
    file_size: int
    mime_type: str | None
    file_name: str | None


_cache: dict[int, tuple[float, ResolvedFile]] = {}


def _extract_media(message) -> ResolvedFile | None:
    media = (
        getattr(message, "video", None)
        or getattr(message, "document", None)
        or getattr(message, "animation", None)
        or getattr(message, "audio", None)
    )
    if media is None:
        return None
    return ResolvedFile(
        file_id=media.file_id,
        file_size=getattr(media, "file_size", 0) or 0,
        mime_type=getattr(media, "mime_type", None),
        file_name=getattr(media, "file_name", None),
    )


async def resolve_source(
    client: Client,
    source_id: int,
    channel_id: int,
    message_id: int,
    fallback_file_id: str,
    fallback_size: int,
) -> ResolvedFile:
    """Return a fresh ResolvedFile for the source, using a short-lived cache."""
    now = time.monotonic()
    cached = _cache.get(source_id)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    resolved: ResolvedFile | None = None
    try:
        message = await client.get_messages(channel_id, message_id)
        if message:
            resolved = _extract_media(message)
    except Exception:
        resolved = None

    if resolved is None:
        # Fall back to the stored file_id if the message could not be read.
        resolved = ResolvedFile(
            file_id=fallback_file_id,
            file_size=fallback_size,
            mime_type=None,
            file_name=None,
        )

    _cache[source_id] = (now, resolved)
    return resolved


def invalidate(source_id: int) -> None:
    _cache.pop(source_id, None)
