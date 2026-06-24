"""Database bootstrap: create tables, seed plans, create main admin."""
import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.models import Plan, User, UserRole

DEFAULT_PLANS = [
    {"name": "Free", "price": 0, "duration_days": 36500, "max_videos": 5,
     "features": "Basic playback"},
    {"name": "Basic", "price": 199, "duration_days": 30, "max_videos": 50,
     "features": "More videos, embed"},
    {"name": "Pro", "price": 499, "duration_days": 30, "max_videos": 500,
     "features": "Multi-quality, multi-audio, ads"},
    {"name": "Premium", "price": 999, "duration_days": 30, "max_videos": 0,
     "features": "Unlimited videos, all features"},
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        for p in DEFAULT_PLANS:
            exists = await session.scalar(select(Plan).where(Plan.name == p["name"]))
            if not exists:
                session.add(Plan(**p))
        await session.commit()

        admin = await session.scalar(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        if not admin:
            session.add(
                User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    role=UserRole.admin,
                    is_active=True,
                )
            )
            await session.commit()
            print(f"Created main admin '{settings.ADMIN_USERNAME}'.")


async def init() -> None:
    await create_tables()
    await seed()
    print("Database initialized.")


if __name__ == "__main__":
    asyncio.run(init())
