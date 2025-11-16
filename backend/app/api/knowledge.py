"""Knowledge Base API endpoints for RAG document management."""

import re
from collections.abc import Generator
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import CurrentUser, get_current_user
from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory

router = APIRouter(prefix="/destinations/{dest_id}/knowledge", tags=["knowledge"])


class KnowledgeItemResponse(BaseModel):
    """Knowledge item response."""

    item_id: UUID
    dest_id: UUID | None
    created_at: str
    status: str  # done | processing | queued
    doc_name: str | None = None


class KnowledgeChunkResponse(BaseModel):
    """Knowledge chunk response."""

    chunk_id: UUID
    item_id: UUID
    snippet: str
    created_at: str
    doc_name: str | None = None


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def strip_pii(text: str) -> str:
    """Strip PII (emails, phone numbers) from text for embedding.

    This is a basic implementation as per SPEC requirements.
    """
    # Strip email addresses
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text
    )
    # Strip phone numbers (basic patterns)
    text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", text)
    text = re.sub(r"\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b", "[PHONE]", text)
    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Chunk text into overlapping segments.

    For PR11, using simple character-based chunking.
    Production would use tiktoken with sentence boundary detection.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters (~1000 tokens)
        overlap: Overlap between chunks in characters

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:  # Only break if we're past halfway
                end = start + break_point + 1
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]  # Filter empty chunks


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_knowledge(
    dest_id: UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Upload and ingest a document for RAG.

    Accepts PDF or Markdown files, chunks them, and creates embeddings.

    Args:
        dest_id: Destination ID
        file: Uploaded file (PDF or MD)
        current_user: Authenticated user context
        session: Database session

    Returns:
        Upload status with item_id
    """
    # Verify destination ownership
    stmt = select(Destination).where(Destination.dest_id == dest_id)
    destination = session.execute(stmt).scalar_one_or_none()

    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )

    if destination.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this destination",
        )

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    file_ext = file.filename.lower().split(".")[-1]
    if file_ext not in ("pdf", "md", "txt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, MD, and TXT files are supported",
        )

    # Read file content
    content_bytes = await file.read()

    # For PR11, simple text extraction
    # Production would use pypdf for PDF parsing
    try:
        if file_ext == "pdf":
            # Stub: for PR11, treat PDF as text (in production, use pypdf2)
            content = content_bytes.decode("utf-8", errors="ignore")
        else:
            content = content_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}",
        ) from e

    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty or unreadable",
        )

    # Create knowledge item
    knowledge_item = KnowledgeItem(
        org_id=current_user.org_id,
        dest_id=dest_id,
        content=content,
        item_metadata={"filename": file.filename, "file_type": file_ext},
    )

    session.add(knowledge_item)
    session.flush()  # Get item_id

    # Chunk the content
    chunks = chunk_text(content)

    # Create embeddings for each chunk (stub for now)
    # In production, this would call OpenAI embedding API
    for chunk_text_content in chunks:
        # Strip PII before embedding
        sanitized_chunk = strip_pii(chunk_text_content)

        # Create embedding record with dummy vector
        # In production, this would be:
        # vector = openai.embeddings.create(input=sanitized_chunk, model="text-embedding-ada-002")
        embedding = Embedding(
            item_id=knowledge_item.item_id,
            chunk_text=chunk_text_content,  # Store original
            chunk_metadata={"sanitized_length": len(sanitized_chunk)},
            # vector field would be populated with actual embeddings in production
        )
        session.add(embedding)

    session.commit()

    return {
        "item_id": str(knowledge_item.item_id),
        "status": "done",
        "chunks_created": len(chunks),
        "filename": file.filename,
    }


@router.get("/items", response_model=list[KnowledgeItemResponse])
def list_knowledge_items(
    dest_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[KnowledgeItemResponse]:
    """List knowledge items for a destination."""
    # Verify destination ownership
    stmt = select(Destination).where(Destination.dest_id == dest_id)
    destination = session.execute(stmt).scalar_one_or_none()

    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )

    if destination.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this destination",
        )

    # Get knowledge items
    stmt = (
        select(KnowledgeItem)
        .where(
            KnowledgeItem.org_id == current_user.org_id,
            KnowledgeItem.dest_id == dest_id,
        )
        .order_by(KnowledgeItem.created_at.desc())
    )
    items = session.execute(stmt).scalars().all()

    results = []
    for item in items:
        doc_name = None
        if item.item_metadata and "filename" in item.item_metadata:
            doc_name = item.item_metadata["filename"]

        results.append(
            KnowledgeItemResponse(
                item_id=item.item_id,
                dest_id=item.dest_id,
                created_at=item.created_at.isoformat(),
                status="done",  # For PR11, all uploads complete synchronously
                doc_name=doc_name,
            )
        )

    return results


@router.get("/chunks", response_model=list[KnowledgeChunkResponse])
def list_knowledge_chunks(
    dest_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[KnowledgeChunkResponse]:
    """List knowledge chunks for a destination."""
    # Verify destination ownership
    stmt = select(Destination).where(Destination.dest_id == dest_id)
    destination = session.execute(stmt).scalar_one_or_none()

    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )

    if destination.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this destination",
        )

    # Get all embeddings for this destination
    stmt = (
        select(Embedding, KnowledgeItem)
        .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
        .where(
            KnowledgeItem.org_id == current_user.org_id,
            KnowledgeItem.dest_id == dest_id,
        )
        .order_by(Embedding.created_at.desc())
        .limit(100)  # Limit to most recent 100 chunks
    )

    results_tuples = session.execute(stmt).all()

    chunks = []
    for embedding, knowledge_item in results_tuples:
        # Get snippet (first 200 chars)
        snippet = embedding.chunk_text[:200] if embedding.chunk_text else ""
        if len(embedding.chunk_text or "") > 200:
            snippet += "..."

        doc_name = None
        if knowledge_item.item_metadata and "filename" in knowledge_item.item_metadata:
            doc_name = knowledge_item.item_metadata["filename"]

        chunks.append(
            KnowledgeChunkResponse(
                chunk_id=embedding.embedding_id,
                item_id=embedding.item_id,
                snippet=snippet,
                created_at=embedding.created_at.isoformat(),
                doc_name=doc_name,
            )
        )

    return chunks
