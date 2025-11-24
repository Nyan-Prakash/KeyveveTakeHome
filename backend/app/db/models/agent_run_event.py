"""Agent run event ORM model for SSE streaming."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .agent_run import AgentRun
    from .org import Org


class AgentRunEvent(Base):
    """Agent run event table - append-only log for SSE streaming."""

    __tablename__ = "agent_run_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_run.run_id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    kind: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # "node_event" | "heartbeat"
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Relationships
    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="events")
    org: Mapped["Org"] = relationship("Org")

    # Constraints
    __table_args__ = (
        Index("idx_event_run_ts", "run_id", "ts"),
        Index("idx_event_org_run", "org_id", "run_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentRunEvent(id={self.id}, run_id={self.run_id}, kind={self.kind!r}, ts={self.ts})>"
