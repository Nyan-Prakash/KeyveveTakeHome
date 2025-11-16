"""Embedding ORM model for pgvector."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from .knowledge_item import KnowledgeItem


class Embedding(Base):
    """Embedding table using pgvector for similarity search."""

    __tablename__ = "embedding"

    embedding_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_item.item_id", ondelete="CASCADE"), nullable=False
    )
    vector: Mapped[Vector | None] = mapped_column(
        Vector(1536), nullable=True
    )  # ada-002 dimension; nullable for PR11 stub
    chunk_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    knowledge_item: Mapped["KnowledgeItem"] = relationship(
        "KnowledgeItem", back_populates="embeddings"
    )

    def __repr__(self) -> str:
        return f"<Embedding(embedding_id={self.embedding_id}, item_id={self.item_id})>"
