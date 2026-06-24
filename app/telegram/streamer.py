"""Low-level MTProto byte streaming.

Telegram's data center file API (`upload.getFile`) returns data in chunks and
requires both the `offset` and `limit` to be aligned to a 1 MiB boundary.
Pyrogram exposes a streaming helper, `Client.stream_media`, which yields 1 MiB
chunks starting at a chosen chunk offset.

This module turns an arbitrary requested byte range [start, end] into:
  1. a chunk-aligned starting offset,
  2. an async generator that yields exactly the requested bytes (trimming the
     first and last partial chunks).

No 20 MB limit applies because this uses MTProto directly (not the Bot API
`getFile`). Files up to 4 GB are supported.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from pyrogram import Client
from pyrogram.file_id import FileId

# Telegram serves file data in 1 MiB chunks.
CHUNK_SIZE = 1024 * 1024


def _aligned_offset(start: int) -> int:
    """Return the 1 MiB-aligned offset at or before `start`."""
    return (start // CHUNK_SIZE) * CHUNK_SIZE


async def stream_range(
    client: Client,
    file_id: str,
    start: int,
    end: int,
) -> AsyncGenerator[bytes, None]:
    """Yield bytes for the inclusive range [start, end] of a Telegram file.

    Pyrogram's `stream_media` accepts an `offset` expressed in CHUNK_SIZE units
    and yields successive 1 MiB chunks from there. We trim the first chunk so
    output begins exactly at `start`, and stop once we have emitted up to and
    including `end`.
    """
    if end < start:
        return

    aligned = _aligned_offset(start)
    chunk_offset = aligned // CHUNK_SIZE  # offset in 1 MiB units
    # Bytes to skip inside the very first chunk.
    skip = start - aligned
    # Total number of bytes we still need to deliver.
    remaining = end - start + 1

    # FileId.decode validates the file_id belongs to a streamable media type.
    FileId.decode(file_id)

    async for chunk in client.stream_media(
        file_id, offset=chunk_offset
    ):  # type: ignore[arg-type]
        if skip:
            chunk = chunk[skip:]
            skip = 0
        if not chunk:
            continue
        if len(chunk) >= remaining:
            yield chunk[:remaining]
            remaining = 0
            break
        yield chunk
        remaining -= len(chunk)

    # If the source was shorter than expected we simply stop; the HTTP layer
    # already advertised Content-Length based on the stored file_size.
