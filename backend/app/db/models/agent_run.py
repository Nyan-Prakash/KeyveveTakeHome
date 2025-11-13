"""Agent run tracking model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import OrgScopedMixin


class AgentRun(Base, OrgScopedMixin):
    """Agent execution run tracking."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_org_user_started", "org_id", "user_id", "started_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    rng_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd_cents: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    plan_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
