"""Itinerary storage model."""

from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import OrgScopedMixin, TimestampMixin


class Itinerary(Base, TimestampMixin, OrgScopedMixin):
    """Generated itinerary storage."""

    __tablename__ = "itineraries"
    __table_args__ = (Index("ix_itineraries_org_id_agent_run_id", "org_id", "agent_run_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(nullable=False)
    itinerary_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
