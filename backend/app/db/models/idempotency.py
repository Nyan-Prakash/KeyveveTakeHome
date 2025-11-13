"""Idempotency key model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import TimestampMixin


class IdempotencyKey(Base, TimestampMixin):
    """Idempotency key for request deduplication."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
        Index("ix_idempotency_keys_ttl_until", "ttl_until"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    ttl_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    headers_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
