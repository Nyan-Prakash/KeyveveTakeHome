"""FastAPI application entry point."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from sqlalchemy.orm import Session

from backend.app.api.health import check_database, check_outbound
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_engine, get_session_factory

# Global state
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Args:
        app: FastAPI application instance.

    Yields:
        None during application lifetime.
    """
    global _engine, _session_factory
    settings = get_settings()
    _engine = get_engine(settings)
    _session_factory = get_session_factory(_engine)
    yield
    if _engine:
        _engine.dispose()


app = FastAPI(title="Keyveve Travel Planner", lifespan=lifespan)


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get database session.

    Yields:
        Database session.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings_dependency() -> Settings:
    """Dependency to get settings.

    Returns:
        Application settings.
    """
    return get_settings()


@app.get("/healthz")
def healthz_endpoint(
    response: Response,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
) -> dict[str, str]:
    """Health check endpoint.

    Checks:
    - Database connectivity
    - Outbound HTTP connectivity

    Args:
        response: FastAPI response object for setting status code.
        session: Database session (injected).
        settings: Application settings (injected).

    Returns:
        Health status dict.
    """
    db_ok, db_status = check_database(session)
    outbound_ok, outbound_status = check_outbound(settings.healthcheck_url)

    all_ok = db_ok and outbound_ok

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if all_ok else "error",
        "db": db_status,
        "outbound": outbound_status,
    }
