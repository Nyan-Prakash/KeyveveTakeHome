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
        # Check if pgvector is available first by testing the extension
        try:
            # Generate query embedding
            search_query = query or f"travel guide information attractions hotels restaurants transportation {city}"

            client = OpenAI(api_key=get_openai_api_key())
            response = client.embeddings.create(
                input=search_query,
                model="text-embedding-ada-002",
            )
            query_vector = response.data[0].embedding

            # Test if pgvector extension is available
            import json
            import numpy as np
            
            pgvector_available = False
            try:
                # Quick test: try to check if vector extension exists
                test_query = session.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                )
                pgvector_available = test_query.scalar()
            except Exception:
                pgvector_available = False
            
            if pgvector_available:
                try:
                    # Semantic search using pgvector cosine distance
                    # Lower distance = more similar
                    stmt = (
                        select(Embedding.chunk_text)
                        .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
                        .where(KnowledgeItem.org_id == org_id)
                        .where(KnowledgeItem.dest_id == destination.dest_id)
                        .where(Embedding.chunk_text.isnot(None))
                        .where(Embedding.vector.isnot(None))
                        .order_by(Embedding.vector.cosine_distance(query_vector))
                        .limit(limit)
                    )

                    results = session.execute(stmt).scalars().all()

                    if results:
                        print(f"✅ RAG: Retrieved {len(results)} chunks via pgvector semantic search")
                        return list(results)
                except Exception as e:
                    print(f"⚠️ RAG: pgvector query failed: {str(e)[:80]}")
                    pgvector_available = False
            
            # Use Python-based similarity if pgvector not available
            if not pgvector_available:
                print(f"⚠️ RAG: pgvector extension not available, using Python-based cosine similarity")
                
                # Fetch all embeddings for this destination
                stmt = (
                    select(Embedding.embedding_id, Embedding.chunk_text, Embedding.vector)
                    .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
                    .where(KnowledgeItem.org_id == org_id)
                    .where(KnowledgeItem.dest_id == destination.dest_id)
                    .where(Embedding.chunk_text.isnot(None))
                    .where(Embedding.vector.isnot(None))
                )
                
                embeddings = session.execute(stmt).all()
                
                if not embeddings:
                    print(f"⚠️ RAG: No embeddings found for {city}")
                else:
                    print(f"🔍 RAG: Computing similarity for {len(embeddings)} embeddings in Python...")
                    
                    similarities = []
                    for emb_id, chunk_text, vector in embeddings:
                        try:
                            # Handle different vector storage formats
                            if isinstance(vector, str):
                                # Vector stored as JSON string
                                vector = json.loads(vector)
                            elif isinstance(vector, bytes):
                                # Vector stored as binary - decode and parse
                                vector = json.loads(vector.decode('utf-8'))
                            elif hasattr(vector, '__iter__') and not isinstance(vector, str):
                                # Already a list/array
                                vector = list(vector)
                            else:
                                # Unknown format, skip
                                continue
                            
                            # Ensure we have a valid list of numbers
                            if not isinstance(vector, list) or len(vector) != 1536:
                                continue
                            
                            # Compute cosine similarity
                            vec_array = np.array(vector, dtype=np.float32)
                            query_array = np.array(query_vector, dtype=np.float32)
                            
                            dot_product = np.dot(query_array, vec_array)
                            query_norm = np.linalg.norm(query_array)
                            vector_norm = np.linalg.norm(vec_array)
                            
                            if query_norm > 0 and vector_norm > 0:
                                similarity = float(dot_product / (query_norm * vector_norm))
                                similarities.append((similarity, chunk_text))
                        except Exception as vec_err:
                            # Skip this embedding if parsing fails
                            print(f"⚠️ Skipping embedding {emb_id}: {str(vec_err)[:50]}")
                            continue
                    
                    if similarities:
                        # Sort by similarity (descending) and take top results
                        similarities.sort(key=lambda x: x[0], reverse=True)
                        results = [text for _, text in similarities[:limit]]
                        
                        print(f"✅ RAG: Retrieved {len(results)} chunks via Python cosine similarity")
                        return results
                    else:
                        print(f"⚠️ RAG: Could not parse any embeddings for {city}")

            # If no results with vectors, fall through to timestamp-based retrieval
            print(f"⚠️ RAG: No embeddings found, falling back to timestamp-based retrieval for {city}")

        except Exception as e:
            # General error in embedding generation or query
            error_msg = str(e)
            print(f"⚠️ RAG: Semantic search failed ({error_msg[:100]}), using timestamp fallback for {city}")

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
