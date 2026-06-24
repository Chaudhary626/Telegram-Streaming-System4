"""Resolve a content slug into a player payload.

Groups a content node's video sources by language, then by quality, and mints a
short-lived signed stream token for each source. The frontend uses this
structure to offer independent language and quality switching: switching one
axis keeps the other fixed (e.g. changing quality preserves the chosen
language, and vice-versa) by indexing into this map.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.security import create_stream_token
from app.db.models import Content, VideoSource

settings = get_settings()

# Order qualities sensibly (highest first); unknown values sort last.
_QUALITY_ORDER = {"2160p": 0, "1440p": 1, "1080p": 2, "720p": 3, "480p": 4,
                  "360p": 5, "240p": 6, "auto": 7}


def _quality_key(q: str) -> int:
    return _QUALITY_ORDER.get(q, 50)


async def get_content_by_slug(
    db: AsyncSession, slug: str
) -> Content | None:
    return await db.scalar(
        select(Content)
        .where(Content.slug == slug)
        .options(selectinload(Content.sources))
    )


async def _collect_sources(
    db: AsyncSession, content: Content
) -> list[VideoSource]:
    """Return the content's own sources, or those of its first child leaves.

    A movie typically holds sources directly; a series/season may not, so we
    fall back to the node's own sources (the watch page targets a leaf, while
    parents are browsed in the panel).
    """
    if content.sources:
        return list(content.sources)
    return []


async def build_player_payload(db: AsyncSession, slug: str) -> dict | None:
    content = await get_content_by_slug(db, slug)
    if content is None:
        return None
    sources = await _collect_sources(db, content)

    # languages: { language: { quality: {src, source_id, size} } }
    languages: dict[str, dict[str, dict]] = {}
    for s in sources:
        token = create_stream_token(s.id)
        url = f"{settings.BASE_URL}/stream/{s.id}?token={token}"
        languages.setdefault(s.language, {})[s.quality] = {
            "source_id": s.id,
            "src": url,
            "size": s.file_size,
            "mime": s.mime_type or "video/mp4",
        }

    # Build ordered lists for the UI.
    lang_list = sorted(languages.keys(), key=lambda x: (x == "original", x))
    quality_by_lang = {
        lang: sorted(languages[lang].keys(), key=_quality_key)
        for lang in languages
    }

    return {
        "title": content.title,
        "slug": content.slug,
        "poster": content.poster_url,
        "languages": languages,
        "lang_list": lang_list,
        "quality_by_lang": quality_by_lang,
        "has_sources": bool(sources),
    }
