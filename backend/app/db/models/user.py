"""User ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .agent_run import AgentRun
    from .itinerary import Itinerary
    from .org import Org
    from .refresh_token import RefreshToken


class User(Base):
    """User table - org-scoped authentication."""

    __tablename__ = "user"

    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Argon2id will be used
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun", back_populates="user"
    )
    itineraries: Mapped[list["Itinerary"]] = relationship(
        "Itinerary", back_populates="user"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_user_org_email"),
        Index("idx_user_org", "org_id"),
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, email={self.email!r}, org_id={self.org_id})>"
