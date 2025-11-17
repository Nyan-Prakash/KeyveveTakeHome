"""RAG retrieval for enriching travel planning with local knowledge."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory


def retrieve_knowledge_for_destination(
    org_id: UUID, city: str, limit: int = 20
) -> list[str]:
    """Retrieve relevant knowledge chunks for a destination.

    Args:
        org_id: Organization ID for scoping
        city: City name to retrieve knowledge for
        limit: Maximum number of chunks to retrieve (default 20)

    Returns:
        List of knowledge chunk texts
    """
    factory = get_session_factory()
    session = factory()

    try:
        # Find the destination for this city (org-scoped)
        dest_stmt = (
            select(Destination)
            .where(Destination.org_id == org_id)
            .where(Destination.city == city)
        )
        destination = session.execute(dest_stmt).scalar_one_or_none()

        if not destination:
            return []

        # Retrieve knowledge chunks for this destination
        # Join embedding → knowledge_item → destination
        stmt = (
            select(Embedding.chunk_text)
            .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
            .where(KnowledgeItem.org_id == org_id)
            .where(KnowledgeItem.dest_id == destination.dest_id)
            .where(Embedding.chunk_text.isnot(None))
            .order_by(Embedding.created_at.desc())
            .limit(limit)
        )

        results = session.execute(stmt).scalars().all()
        return list(results)

    finally:
        session.close()
