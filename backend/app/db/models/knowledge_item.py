"""Knowledge item ORM model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .destination import Destination
    from .embedding import Embedding
    from .org import Org


class KnowledgeItem(Base):
    """Knowledge item table for RAG corpus."""

    __tablename__ = "knowledge_item"

    item_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("org.org_id", ondelete="CASCADE"), nullable=False
    )
    dest_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("destination.dest_id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    item_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="knowledge_items")
    destination: Mapped["Destination | None"] = relationship(
        "Destination", back_populates="knowledge_items"
    )
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding", back_populates="knowledge_item", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (Index("idx_knowledge_org_dest", "org_id", "dest_id"),)

    def __repr__(self) -> str:
        return f"<KnowledgeItem(item_id={self.item_id}, org_id={self.org_id}, dest_id={self.dest_id})>"
