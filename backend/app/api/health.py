"""Health check endpoint for monitoring."""

import httpx
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import Settings

router = APIRouter()


def check_database(session: Session) -> tuple[bool, str]:
    """Check database connectivity.

    Args:
        session: Database session.

    Returns:
        Tuple of (success, status_string).
    """
    try:
        session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception:
        return False, "error"


def check_outbound(
    healthcheck_url: str, timeout_seconds: float = 1.0
) -> tuple[bool, str]:
    """Check outbound HTTP connectivity.

    Args:
        healthcheck_url: URL to check.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Tuple of (success, status_string).
    """
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.head(healthcheck_url, follow_redirects=True)
            response.raise_for_status()
        return True, "ok"
    except Exception:
        return False, "error"


@router.get("/healthz")
def healthz(
    response: Response,
    session: Session,
    settings: Settings,
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
