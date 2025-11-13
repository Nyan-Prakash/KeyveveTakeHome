"""Centralized session management for the application."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import get_engine, get_session_factory

# Module-level engine and session factory
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_db() -> None:
    """Initialize the database engine and session factory."""
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = get_engine(settings)
        _session_factory = get_session_factory(_engine)


def get_db_engine() -> Engine:
    """Get the global database engine.

    Returns:
        SQLAlchemy engine instance.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


def get_db_session_factory() -> sessionmaker[Session]:
    """Get the global session factory.

    Returns:
        Session factory.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    return _session_factory
