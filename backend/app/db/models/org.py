"""Organization ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .agent_run import AgentRun
    from .destination import Destination
    from .itinerary import Itinerary
    from .knowledge_item import KnowledgeItem
    from .user import User


class Org(Base):
    """Organization table - root of multi-tenancy hierarchy."""

    __tablename__ = "org"

    org_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="org", cascade="all, delete-orphan"
    )
    destinations: Mapped[list["Destination"]] = relationship(
        "Destination", back_populates="org", cascade="all, delete-orphan"
    )
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        "KnowledgeItem", back_populates="org", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun", back_populates="org", cascade="all, delete-orphan"
    )
    itineraries: Mapped[list["Itinerary"]] = relationship(
        "Itinerary", back_populates="org", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Org(org_id={self.org_id}, name={self.name!r})>"
