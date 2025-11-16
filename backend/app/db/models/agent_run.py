"""Agent run ORM model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .agent_run_event import AgentRunEvent
    from .itinerary import Itinerary
    from .org import Org
    from .user import User


class AgentRun(Base):
    """Agent run table - tracks LangGraph execution state."""

    __tablename__ = "agent_run"

    run_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False
    )
    intent: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    plan_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    tool_log: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # running | completed | error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="agent_runs")
    user: Mapped["User"] = relationship("User", back_populates="agent_runs")
    itineraries: Mapped[list["Itinerary"]] = relationship(
        "Itinerary", back_populates="agent_run"
    )
    events: Mapped[list["AgentRunEvent"]] = relationship(
        "AgentRunEvent", back_populates="agent_run", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (Index("idx_run_org_user", "org_id", "user_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<AgentRun(run_id={self.run_id}, org_id={self.org_id}, user_id={self.user_id}, status={self.status!r})>"
