"""Destination ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .knowledge_item import KnowledgeItem
    from .org import Org


class Destination(Base):
    """Destination table - org-scoped travel destinations."""

    __tablename__ = "destination"

    dest_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    city: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    geo: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # {lat: float, lon: float}
    fixture_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="destinations")
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        "KnowledgeItem", back_populates="destination"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "org_id", "city", "country", name="uq_destination_org_city_country"
        ),
    )

    def __repr__(self) -> str:
        return f"<Destination(dest_id={self.dest_id}, city={self.city!r}, country={self.country!r}, org_id={self.org_id})>"
