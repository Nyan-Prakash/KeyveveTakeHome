"""Itinerary ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .agent_run import AgentRun
    from .org import Org
    from .user import User


class Itinerary(Base):
    """Itinerary table - final user-facing travel plans."""

    __tablename__ = "itinerary"

    itinerary_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_run.run_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # ItineraryV1 JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="itineraries")
    user: Mapped["User"] = relationship("User", back_populates="itineraries")
    agent_run: Mapped["AgentRun"] = relationship(
        "AgentRun", back_populates="itineraries"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("org_id", "itinerary_id", name="uq_itinerary_org_id"),
        Index("idx_itinerary_org_user", "org_id", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Itinerary(itinerary_id={self.itinerary_id}, org_id={self.org_id}, user_id={self.user_id})>"
