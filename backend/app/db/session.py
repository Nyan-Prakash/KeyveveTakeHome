"""Database session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings

# Create engine - singleton pattern
_engine = None
_session_factory = None


def get_engine():
    """Get SQLAlchemy engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.postgres_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get session factory singleton."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    """
    Get a database session for use in tests and scripts.

    Yields a session and ensures it is properly closed.

    Example:
        with next(get_session()) as session:
            # Use session
            pass
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
