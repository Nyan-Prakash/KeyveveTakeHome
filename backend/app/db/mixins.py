"""Mixins for common ORM model patterns."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Mixin providing created_at and deleted_at timestamp fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class OrgScopedMixin:
    """Mixin for models scoped to an organization."""

    org_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
