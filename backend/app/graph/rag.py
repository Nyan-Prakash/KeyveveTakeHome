"""RAG retrieval for enriching travel planning with local knowledge."""

from uuid import UUID

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_openai_api_key
from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory


def retrieve_knowledge_for_destination(
    org_id: UUID,
    city: str,
    limit: int = 20,
    query: str | None = None,
) -> list[str]:
    """Retrieve relevant knowledge chunks for a destination using semantic search.

    Uses OpenAI embeddings and pgvector similarity search to find the most
    relevant chunks based on the query. Falls back to timestamp-based retrieval
    if semantic search fails.

    Args:
        org_id: Organization ID for scoping
        city: City name to retrieve knowledge for
        limit: Maximum number of chunks to retrieve (default 20)
        query: Optional search query for semantic retrieval. If None, uses
               a generic query about the city.

    Returns:
        List of knowledge chunk texts, ordered by relevance
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

        # Attempt semantic search with embeddings
        try:
            # Generate query embedding
            search_query = query or f"travel guide information attractions hotels restaurants transportation {city}"

            client = OpenAI(api_key=get_openai_api_key())
            response = client.embeddings.create(
                input=search_query,
                model="text-embedding-ada-002",
            )
            query_vector = response.data[0].embedding

            # Semantic search using pgvector cosine distance
            # Lower distance = more similar
            stmt = (
                select(Embedding.chunk_text)
                .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
                .where(KnowledgeItem.org_id == org_id)
                .where(KnowledgeItem.dest_id == destination.dest_id)
                .where(Embedding.chunk_text.isnot(None))
                .where(Embedding.vector.isnot(None))  # Only chunks with embeddings
                .order_by(Embedding.vector.cosine_distance(query_vector))
                .limit(limit)
            )

            results = session.execute(stmt).scalars().all()

            # If we got semantic results, return them
            if results:
                print(f"RAG: Retrieved {len(results)} chunks via semantic search for '{search_query[:50]}...'")
                return list(results)

            # If no results with vectors, fall through to timestamp-based retrieval
            print(f"RAG: No embeddings found, falling back to timestamp-based retrieval for {city}")

        except Exception as e:
            # Log error and fall back to timestamp-based retrieval
            print(f"RAG: Semantic search failed ({str(e)}), using timestamp fallback for {city}")

        # Fallback: Retrieve chunks by recency (original behavior)
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
