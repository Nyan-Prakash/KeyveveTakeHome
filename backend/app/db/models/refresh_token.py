"""Refresh token ORM model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .user import User


class RefreshToken(Base):
    """Refresh token table for JWT authentication."""

    __tablename__ = "refresh_token"

    token_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # SHA-256 hash of token
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    # Constraints
    __table_args__ = (Index("idx_refresh_user", "user_id", "revoked"),)

    def __repr__(self) -> str:
        return f"<RefreshToken(token_id={self.token_id}, user_id={self.user_id}, revoked={self.revoked})>"
