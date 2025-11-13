"""User model."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import OrgScopedMixin, TimestampMixin


class User(Base, TimestampMixin, OrgScopedMixin):
    """User entity."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_user_org_email"),
        Index("ix_users_org_id_email", "org_id", "email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
