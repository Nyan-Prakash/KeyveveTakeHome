"""Idempotency ORM model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class IdempotencyEntry(Base):
    """Idempotency table for request deduplication."""

    __tablename__ = "idempotency"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        nullable=False
    )  # FK-ish, not enforced for flexibility
    org_id: Mapped[UUID] = mapped_column(nullable=False)  # For tenancy safety
    ttl_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # pending | completed | error
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    headers_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Constraints
    __table_args__ = (
        Index(
            "idx_idempotency_ttl", "ttl_until", postgresql_where="status = 'completed'"
        ),
    )

    def __repr__(self) -> str:
        return f"<IdempotencyEntry(key={self.key!r}, user_id={self.user_id}, status={self.status!r})>"
