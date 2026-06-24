"""ORM models mirroring the SQL schema in db/schema.sql."""
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    subadmin = "subadmin"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ContentType(str, enum.Enum):
    movie = "movie"
    series = "series"
    season = "season"
    episode = "episode"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.subadmin, nullable=False
    )
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plan: Mapped["Plan"] = relationship(back_populates="users")
    contents: Mapped[list["Content"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    payments: Mapped[list["PaymentRequest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_videos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    features: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="plan")


class Content(Base, TimestampMixin):
    """Hierarchical content node: movie/series -> season -> episode."""

    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_owner_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ContentType] = mapped_column(
        Enum(ContentType), default=ContentType.movie, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="contents")
    parent: Mapped["Content"] = relationship(
        remote_side="Content.id", back_populates="children"
    )
    children: Mapped[list["Content"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    sources: Mapped[list["VideoSource"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )


class VideoSource(Base, TimestampMixin):
    """A single video file (one language+quality variant) for a content leaf."""

    __tablename__ = "video_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_unique_id: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(32), default="original", nullable=False)
    quality: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)

    content: Mapped["Content"] = relationship(back_populates="sources")


class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PaymentRequest(Base, TimestampMixin):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transaction_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
