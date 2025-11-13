"""Embedding ORM model for pgvector."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey
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
    vector: Mapped[Vector] = mapped_column(
        Vector(1536), nullable=False
    )  # ada-002 dimension
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(datetime.UTC),
    )

    # Relationships
    knowledge_item: Mapped["KnowledgeItem"] = relationship(
        "KnowledgeItem", back_populates="embeddings"
    )

    def __repr__(self) -> str:
        return f"<Embedding(embedding_id={self.embedding_id}, item_id={self.item_id})>"
