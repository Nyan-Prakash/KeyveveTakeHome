"""Organization model."""

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.db.mixins import TimestampMixin


class Org(Base, TimestampMixin):
    """Organization entity."""

    __tablename__ = "orgs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
