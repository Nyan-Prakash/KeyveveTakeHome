"""Idempotency store for request deduplication.

This module provides a pure, database-backed idempotency store
that will later be used to wrap HTTP endpoints.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models.idempotency import IdempotencyEntry


def get_entry(session: Session, key: str) -> IdempotencyEntry | None:
    """
    Get an idempotency entry by key.

    Args:
        session: SQLAlchemy session
        key: Idempotency key

    Returns:
        IdempotencyEntry if found and not expired, None otherwise

    Note:
        Expired entries (ttl_until < now) are treated as missing.
    """
    entry = session.get(IdempotencyEntry, key)

    if entry is None:
        return None

    # Check if entry has expired
    now = datetime.now(timezone.utc)
    if entry.ttl_until < now:
        return None

    return entry


def save_result(
    session: Session,
    key: str,
    user_id: UUID,
    org_id: UUID,
    status: str,
    body_hash: str,
    headers_hash: str,
    ttl_seconds: int = 86400,  # 24 hours default
) -> IdempotencyEntry:
    """
    Save or update an idempotency entry.

    Args:
        session: SQLAlchemy session
        key: Idempotency key
        user_id: User ID making the request
        org_id: Organization ID for tenancy
        status: Entry status (pending | completed | error)
        body_hash: Hash of request body
        headers_hash: Hash of relevant headers
        ttl_seconds: Time-to-live in seconds (default: 24h)

    Returns:
        Created or updated IdempotencyEntry

    Example:
        entry = save_result(
            session,
            key="req-123",
            user_id=user_id,
            org_id=org_id,
            status="completed",
            body_hash="abc123",
            headers_hash="def456",
            ttl_seconds=86400
        )
    """
    now = datetime.now(timezone.utc)
    ttl_until = now + timedelta(seconds=ttl_seconds)

    # Check if entry exists
    existing = session.get(IdempotencyEntry, key)

    if existing:
        # Update existing entry
        existing.status = status
        existing.body_hash = body_hash
        existing.headers_hash = headers_hash
        existing.ttl_until = ttl_until
        session.flush()
        return existing
    else:
        # Create new entry
        entry = IdempotencyEntry(
            key=key,
            user_id=user_id,
            org_id=org_id,
            status=status,
            body_hash=body_hash,
            headers_hash=headers_hash,
            ttl_until=ttl_until,
            created_at=now,
        )
        session.add(entry)
        session.flush()
        return entry


def mark_completed(
    session: Session,
    key: str,
    body_hash: str,
    headers_hash: str,
) -> IdempotencyEntry | None:
    """
    Mark an idempotency entry as completed.

    Args:
        session: SQLAlchemy session
        key: Idempotency key
        body_hash: Hash of response body
        headers_hash: Hash of response headers

    Returns:
        Updated IdempotencyEntry if found, None otherwise

    Example:
        entry = mark_completed(
            session,
            key="req-123",
            body_hash="response-abc",
            headers_hash="response-def"
        )
    """
    entry = session.get(IdempotencyEntry, key)

    if entry is None:
        return None

    entry.status = "completed"
    entry.body_hash = body_hash
    entry.headers_hash = headers_hash
    session.flush()

    return entry


def mark_error(session: Session, key: str) -> IdempotencyEntry | None:
    """
    Mark an idempotency entry as errored.

    Args:
        session: SQLAlchemy session
        key: Idempotency key

    Returns:
        Updated IdempotencyEntry if found, None otherwise
    """
    entry = session.get(IdempotencyEntry, key)

    if entry is None:
        return None

    entry.status = "error"
    session.flush()

    return entry
