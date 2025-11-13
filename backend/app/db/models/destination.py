"""Destination model."""

from uuid import UUID, uuid4

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import OrgScopedMixin, TimestampMixin


class Destination(Base, TimestampMixin, OrgScopedMixin):
    """Destination entity."""

    __tablename__ = "destinations"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_destination_org_slug"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
