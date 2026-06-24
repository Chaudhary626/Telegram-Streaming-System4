"""Reusable content/user/source service logic.

Shared by the Telegram bot (Phase 3) and the web panels (Phase 4+). Every read
and write is scoped by `owner_id` so a subadmin can never see or touch another
user's content (strict user isolation).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.utils import slugify
from app.db.models import Content, ContentType, User, UserRole, VideoSource


async def get_or_create_user_by_tg(
    db: AsyncSession, telegram_id: int, username_hint: str
) -> User:
    """Resolve a Telegram user to a subadmin User row, creating it if needed."""
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        return user

    # Build a unique, stable username for the panel login.
    base = slugify(username_hint or f"tg{telegram_id}")
    candidate = base
    suffix = 0
    while await db.scalar(select(User).where(User.username == candidate)):
        suffix += 1
        candidate = f"{base}-{suffix}"

    user = User(
        username=candidate,
        password_hash="!tg-login-only",  # panel password set separately
        role=UserRole.subadmin,
        telegram_id=telegram_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _unique_slug(db: AsyncSession, owner_id: int, base: str) -> str:
    candidate = base
    suffix = 0
    while await db.scalar(
        select(Content).where(
            Content.owner_id == owner_id, Content.slug == candidate
        )
    ):
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _infer_type(depth: int) -> ContentType:
    """Map hierarchy depth to a content type.

    depth 0 -> movie/series root, 1 -> season, 2+ -> episode.
    """
    if depth == 0:
        return ContentType.movie
    if depth == 1:
        return ContentType.season
    return ContentType.episode


async def create_content_node(
    db: AsyncSession,
    owner_id: int,
    title: str,
    parent: Content | None = None,
    content_type: ContentType | None = None,
) -> Content:
    depth = 0
    if parent is not None:
        # Walk up to compute depth for type inference.
        node = parent
        depth = 1
        while node.parent_id is not None:
            depth += 1
            node = await db.scalar(
                select(Content).where(Content.id == node.parent_id)
            )
            if node is None:
                break

    ctype = content_type or _infer_type(depth)
    base_slug = slugify(title)
    if parent is not None:
        base_slug = f"{parent.slug}-{base_slug}"
    slug = await _unique_slug(db, owner_id, base_slug)

    content = Content(
        owner_id=owner_id,
        parent_id=parent.id if parent else None,
        title=title.strip(),
        slug=slug,
        type=ctype,
    )
    db.add(content)
    await db.flush()
    return content


async def create_content_path(
    db: AsyncSession, owner_id: int, path: str
) -> Content:
    """Create a hierarchy from a slash-separated path, reusing existing nodes.

    Example: 'Movie/Season 1/Episode 1' creates/links three levels and returns
    the leaf node.
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Empty content path")

    parent: Content | None = None
    for idx, part in enumerate(parts):
        # Try to reuse an existing sibling with the same title under parent.
        existing = await db.scalar(
            select(Content).where(
                Content.owner_id == owner_id,
                Content.parent_id == (parent.id if parent else None),
                Content.title == part,
            )
        )
        if existing:
            parent = existing
            continue
        parent = await create_content_node(
            db, owner_id, part, parent=parent
        )
    return parent  # type: ignore[return-value]


async def list_user_contents(
    db: AsyncSession, owner_id: int, parent_id: int | None = None
) -> list[Content]:
    rows = await db.scalars(
        select(Content)
        .where(Content.owner_id == owner_id, Content.parent_id == parent_id)
        .order_by(Content.created_at.desc())
    )
    return list(rows)


async def get_owned_content(
    db: AsyncSession, owner_id: int, content_id: int
) -> Content | None:
    """Fetch a content node ONLY if it belongs to owner_id (isolation)."""
    return await db.scalar(
        select(Content)
        .where(Content.id == content_id, Content.owner_id == owner_id)
        .options(selectinload(Content.sources))
    )


async def add_video_source(
    db: AsyncSession,
    content: Content,
    *,
    channel_id: int,
    message_id: int,
    file_id: str,
    file_unique_id: str,
    file_size: int,
    file_name: str | None,
    mime_type: str | None,
    language: str,
    quality: str,
) -> VideoSource:
    source = VideoSource(
        content_id=content.id,
        channel_id=channel_id,
        message_id=message_id,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_size=file_size,
        file_name=file_name,
        mime_type=mime_type,
        language=language,
        quality=quality,
    )
    db.add(source)
    await db.flush()
    return source


async def count_user_videos(db: AsyncSession, owner_id: int) -> int:
    rows = await db.scalars(
        select(VideoSource.id)
        .join(Content, VideoSource.content_id == Content.id)
        .where(Content.owner_id == owner_id)
    )
    return len(list(rows))
