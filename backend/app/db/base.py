"""Database base configuration and utilities."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import Settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def get_engine(settings: Settings) -> Engine:
    """Create and configure a SQLAlchemy engine.

    Args:
        settings: Application settings containing database URL.

    Returns:
        Configured SQLAlchemy engine.
    """
    return create_engine(
        settings.postgres_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory for the given engine.

    Args:
        engine: SQLAlchemy engine to bind sessions to.

    Returns:
        Session factory.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Args:
        session_factory: Session factory to create sessions from.

    Yields:
        Database session.

    Example:
        >>> from backend.app.config import get_settings
        >>> settings = get_settings()
        >>> engine = get_engine(settings)
        >>> factory = get_session_factory(engine)
        >>> with get_session(factory) as session:
        ...     session.query(User).all()
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
