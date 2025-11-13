"""Knowledge base models."""

from uuid import UUID, uuid4

from sqlalchemy import Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import OrgScopedMixin, TimestampMixin


class KnowledgeItem(Base, TimestampMixin, OrgScopedMixin):
    """Knowledge item for a destination."""

    __tablename__ = "knowledge_items"
    __table_args__ = (Index("ix_knowledge_items_org_id_destination_id", "org_id", "destination_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    destination_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


class Embedding(Base, TimestampMixin, OrgScopedMixin):
    """Vector embedding for knowledge items."""

    __tablename__ = "embeddings"
    __table_args__ = (Index("ix_embeddings_org_id_knowledge_item_id", "org_id", "knowledge_item_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    knowledge_item_id: Mapped[UUID] = mapped_column(nullable=False)
    # Using BYTEA for now; replace with pgvector extension later if needed
    vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
