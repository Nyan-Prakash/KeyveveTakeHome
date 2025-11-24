"""Knowledge Base API endpoints for RAG document management."""

import re
import time
from collections.abc import Generator
from typing import Any
from uuid import UUID

import tiktoken
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import CurrentUser, get_current_user
from backend.app.config import get_openai_api_key, get_settings
from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory
from backend.app.utils.pdf_parser import extract_text_from_pdf, PDFParsingError

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
    # Strip phone numbers (various patterns)
    # Pattern 1: (555) 987-6543
    text = re.sub(r"\(\d{3}\)\s*\d{3}[-.]?\d{4}", "[PHONE]", text)
    # Pattern 2: 555-123-4567
    text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", text)
    return text


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Chunk text into overlapping segments using token-aware chunking.

    Uses tiktoken to ensure chunks are properly sized for OpenAI embeddings.
    Attempts to break at sentence boundaries when possible.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens (default 800, optimal for embeddings)
        overlap: Overlap between chunks in tokens (default 100)

    Returns:
        List of text chunks
    """
    try:
        # Get encoding for text-embedding-ada-002 model
        encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    except KeyError:
        # Fallback to cl100k_base encoding if model not found
        encoding = tiktoken.get_encoding("cl100k_base")

    # Encode the entire text into tokens
    tokens = encoding.encode(text)

    chunks = []
    start = 0

    while start < len(tokens):
        # Calculate end position
        end = min(start + chunk_size, len(tokens))

        # Extract chunk tokens
        chunk_tokens = tokens[start:end]

        # Decode back to text
        chunk_text = encoding.decode(chunk_tokens)

        # Try to break at sentence boundary if not at the end
        if end < len(tokens):
            # Look for sentence endings in the last 20% of the chunk
            search_start = int(len(chunk_text) * 0.8)
            remaining = chunk_text[search_start:]

            # Find last sentence boundary
            last_period = remaining.rfind(". ")
            last_question = remaining.rfind("? ")
            last_exclamation = remaining.rfind("! ")
            last_newline = remaining.rfind("\n\n")

            break_point = max(last_period, last_question, last_exclamation, last_newline)

            if break_point != -1:
                # Break at sentence boundary (include the punctuation)
                chunk_text = chunk_text[: search_start + break_point + 1].strip()
                # Recalculate actual token count for next iteration
                actual_tokens_used = len(encoding.encode(chunk_text))
                start = start + actual_tokens_used - overlap
            else:
                # No good break point found, use full chunk
                start = end - overlap

        # Add chunk if it has content
        if chunk_text.strip():
            chunks.append(chunk_text.strip())

        # Move to next chunk if we haven't found a sentence boundary
        if end >= len(tokens):
            break

    # Remove duplicates while preserving order
    seen = set()
    unique_chunks = []
    for chunk in chunks:
        if chunk and chunk not in seen:
            seen.add(chunk)
            unique_chunks.append(chunk)

    return unique_chunks


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

    # Extract text based on file type
    settings = get_settings()

    try:
        if file_ext == "pdf":
            # Use PyMuPDF + OCR for PDF text extraction
            try:
                content = extract_text_from_pdf(
                    content_bytes,
                    use_ocr=settings.enable_pdf_ocr,
                    ocr_threshold=settings.ocr_min_text_threshold,
                    ocr_dpi_scale=settings.ocr_dpi_scale,
                )
            except PDFParsingError as pdf_error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF parsing failed: {str(pdf_error)}",
                ) from pdf_error
        else:
            # Plain text files (.md, .txt)
            content = content_bytes.decode("utf-8")
    except HTTPException:
        raise
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
    print(f"\n{'='*60}")
    print(f"KNOWLEDGE UPLOAD: {file.filename}")
    print(f"{'='*60}")
    print(f"File size: {len(content)} characters")

    chunks = chunk_text(content)
    print(f"✓ Chunked into {len(chunks)} segments")

    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=get_openai_api_key())
        print(f"✓ OpenAI client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize OpenAI client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize OpenAI client: {str(e)}",
        ) from e

    # Generate embeddings for each chunk
    embeddings_created = 0
    embeddings_failed = 0

    # Process chunks in batches of 100 (OpenAI API limit)
    batch_size = 100
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    print(f"\n📊 Processing {len(chunks)} chunks in {total_batches} batch(es)...")

    for i in range(0, len(chunks), batch_size):
        batch_num = (i // batch_size) + 1
        batch_chunks = chunks[i : i + batch_size]

        print(f"\n  Batch {batch_num}/{total_batches}: Processing {len(batch_chunks)} chunks...")

        # Prepare sanitized chunks for embedding
        sanitized_batch = [strip_pii(chunk) for chunk in batch_chunks]

        try:
            # Generate embeddings for batch
            print(f"    → Calling OpenAI embeddings API...")
            start_time = time.time()

            response = client.embeddings.create(
                input=sanitized_batch,
                model="text-embedding-ada-002",
            )

            api_time = time.time() - start_time
            print(f"    ✓ API responded in {api_time:.2f}s")

            # Create embedding records with vectors
            print(f"    → Storing embeddings in database...")
            for j, chunk_text_content in enumerate(batch_chunks):
                vector = response.data[j].embedding  # 1536-dimensional array

                embedding = Embedding(
                    item_id=knowledge_item.item_id,
                    chunk_text=chunk_text_content,  # Store original
                    vector=vector,  # Store the embedding vector
                    chunk_metadata={
                        "sanitized_length": len(sanitized_batch[j]),
                        "token_count": len(tiktoken.encoding_for_model("text-embedding-ada-002").encode(chunk_text_content)),
                    },
                )
                session.add(embedding)
                embeddings_created += 1

            print(f"    ✓ Batch {batch_num} complete: {len(batch_chunks)} embeddings created")

        except Exception as e:
            # Log error but continue processing other batches
            embeddings_failed += len(batch_chunks)
            print(f"    ✗ Batch {batch_num} FAILED: {e}")
            print(f"    → Creating fallback records without embeddings...")

            # Create embedding records without vectors as fallback
            for chunk_text_content in batch_chunks:
                sanitized_chunk = strip_pii(chunk_text_content)
                embedding = Embedding(
                    item_id=knowledge_item.item_id,
                    chunk_text=chunk_text_content,
                    vector=None,  # No vector due to API failure
                    chunk_metadata={
                        "sanitized_length": len(sanitized_chunk),
                        "embedding_failed": True,
                        "error": str(e)[:200],  # Truncate error message
                    },
                )
                session.add(embedding)

            print(f"    ✓ Fallback records created")

    print(f"\n📝 Committing to database...")
    session.commit()
    print(f"✓ Database commit successful")

    # Print summary
    print(f"\n{'='*60}")
    print(f"UPLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"Filename: {file.filename}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Embeddings generated: {embeddings_created}")
    print(f"Embeddings failed: {embeddings_failed}")
    print(f"Success rate: {embeddings_created / len(chunks) * 100:.1f}%")
    print(f"{'='*60}\n")

    return {
        "item_id": str(knowledge_item.item_id),
        "status": "done",
        "chunks_created": len(chunks),
        "embeddings_created": embeddings_created,
        "embeddings_failed": embeddings_failed,
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
