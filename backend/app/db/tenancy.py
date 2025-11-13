"""Tenancy enforcement helpers for org-scoped queries.

This module provides explicit, testable helpers to scope queries by org_id,
ensuring multi-tenant data isolation without magical event hooks.
"""

from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

# Type variable for ORM models
T = TypeVar("T")


def scoped_query(
    session: Session, model: type[T], org_id: UUID, **filters: Any
) -> Select[tuple[T]]:
    """
    Create an org-scoped query for a model.

    Args:
        session: SQLAlchemy session
        model: ORM model class (must have org_id column)
        org_id: Organization ID to scope query to
        **filters: Additional filter conditions (column=value)

    Returns:
        SQLAlchemy Select statement with org_id filter applied

    Example:
        stmt = scoped_query(session, Itinerary, org_id, user_id=user_id)
        results = session.execute(stmt).scalars().all()

    Raises:
        AttributeError: If model doesn't have org_id column
    """
    if not hasattr(model, "org_id"):
        raise AttributeError(f"Model {model.__name__} does not have org_id column")

    stmt = select(model).where(model.org_id == org_id)

    # Apply additional filters
    for key, value in filters.items():
        if not hasattr(model, key):
            raise AttributeError(f"Model {model.__name__} does not have {key} column")
        stmt = stmt.where(getattr(model, key) == value)

    return stmt


def scoped_get(
    session: Session, model: type[T], org_id: UUID, **filters: Any
) -> T | None:
    """
    Get a single org-scoped record.

    Args:
        session: SQLAlchemy session
        model: ORM model class (must have org_id column)
        org_id: Organization ID to scope query to
        **filters: Filter conditions (column=value)

    Returns:
        Single model instance or None if not found

    Example:
        itinerary = scoped_get(session, Itinerary, org_id, itinerary_id=itin_id)
    """
    stmt = scoped_query(session, model, org_id, **filters)
    return session.execute(stmt).scalar_one_or_none()


def scoped_list(
    session: Session,
    model: type[T],
    org_id: UUID,
    limit: int | None = None,
    offset: int | None = None,
    **filters: Any,
) -> list[T]:
    """
    Get a list of org-scoped records.

    Args:
        session: SQLAlchemy session
        model: ORM model class (must have org_id column)
        org_id: Organization ID to scope query to
        limit: Maximum number of records to return
        offset: Number of records to skip
        **filters: Filter conditions (column=value)

    Returns:
        List of model instances

    Example:
        itineraries = scoped_list(session, Itinerary, org_id, user_id=user_id, limit=10)
    """
    stmt = scoped_query(session, model, org_id, **filters)

    if offset is not None:
        stmt = stmt.offset(offset)

    if limit is not None:
        stmt = stmt.limit(limit)

    return list(session.execute(stmt).scalars().all())


def scoped_count(session: Session, model: type[T], org_id: UUID, **filters: Any) -> int:
    """
    Count org-scoped records.

    Args:
        session: SQLAlchemy session
        model: ORM model class (must have org_id column)
        org_id: Organization ID to scope query to
        **filters: Filter conditions (column=value)

    Returns:
        Count of matching records

    Example:
        count = scoped_count(session, Itinerary, org_id, user_id=user_id)
    """
    from sqlalchemy import func

    stmt = scoped_query(session, model, org_id, **filters)
    # Replace select columns with count
    stmt = select(func.count()).select_from(stmt.subquery())
    result = session.execute(stmt).scalar()
    return result or 0


class TenantRepository:
    """
    Base repository class that enforces org-scoped queries.

    This provides a simple, explicit way to ensure all queries include org_id.
    Subclasses can add model-specific methods while maintaining tenancy safety.
    """

    def __init__(self, session: Session, org_id: UUID):
        """
        Initialize repository with session and org context.

        Args:
            session: SQLAlchemy session
            org_id: Organization ID for this repository instance
        """
        self.session = session
        self.org_id = org_id

    def query(self, model: type[T], **filters: Any) -> Select[tuple[T]]:
        """Create an org-scoped query."""
        return scoped_query(self.session, model, self.org_id, **filters)

    def get(self, model: type[T], **filters: Any) -> T | None:
        """Get a single org-scoped record."""
        return scoped_get(self.session, model, self.org_id, **filters)

    def list(
        self,
        model: type[T],
        limit: int | None = None,
        offset: int | None = None,
        **filters: Any,
    ) -> list[T]:
        """Get a list of org-scoped records."""
        return scoped_list(
            self.session, model, self.org_id, limit=limit, offset=offset, **filters
        )

    def count(self, model: type[T], **filters: Any) -> int:
        """Count org-scoped records."""
        return scoped_count(self.session, model, self.org_id, **filters)
