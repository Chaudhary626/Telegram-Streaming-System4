"""HTTP streaming endpoints backed by MTProto.

Routes:
  GET /stream/{source_id}?token=...   -> ranged media stream

The token is a signed stream token (see app.core.security.create_stream_token)
so stream URLs are not guessable and can expire. The player layer (Phase 5)
mints these tokens; for manual testing you can generate one with the helper
endpoint exposed only in development.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ranges import parse_range
from app.core.security import create_stream_token, decode_stream_token
from app.db.base import get_db
from app.db.models import VideoSource
from app.telegram.client import tg_client
from app.telegram.resolver import resolve_source
from app.telegram.streamer import stream_range

router = APIRouter(tags=["stream"])
settings = get_settings()


async def _load_source(db: AsyncSession, source_id: int) -> VideoSource:
    source = await db.scalar(select(VideoSource).where(VideoSource.id == source_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/stream/{source_id}")
async def stream_source(
    source_id: int,
    request: Request,
    token: str,
    range_header: str | None = Header(default=None, alias="Range"),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_stream_token(token)
    if not payload or payload.get("sid") != source_id:
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    source = await _load_source(db, source_id)

    client = await tg_client.start()
    resolved = await resolve_source(
        client,
        source_id=source.id,
        channel_id=source.channel_id,
        message_id=source.message_id,
        fallback_file_id=source.file_id,
        fallback_size=source.file_size,
    )

    file_size = resolved.file_size or source.file_size
    if file_size <= 0:
        raise HTTPException(status_code=422, detail="Unknown file size")

    br = parse_range(range_header, file_size)
    content_type = resolved.mime_type or source.mime_type or "video/mp4"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {br.start}-{br.end}/{file_size}",
        "Content-Length": str(br.length),
        "Content-Disposition": "inline",
        "Cache-Control": "no-store",
    }

    body = stream_range(client, resolved.file_id, br.start, br.end)
    status_code = 206 if range_header else 200
    if not range_header:
        # Full-file response still benefits from advertising the length.
        headers.pop("Content-Range", None)
    return StreamingResponse(
        body,
        status_code=status_code,
        media_type=content_type,
        headers=headers,
    )


@router.get("/stream-token/{source_id}")
async def dev_stream_token(source_id: int, db: AsyncSession = Depends(get_db)):
    """Development-only helper to mint a stream token for manual testing."""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    await _load_source(db, source_id)
    token = create_stream_token(source_id)
    return {
        "source_id": source_id,
        "token": token,
        "url": f"{settings.BASE_URL}/stream/{source_id}?token={token}",
    }
