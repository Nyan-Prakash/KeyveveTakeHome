"""Health check endpoint for infrastructure status."""

from typing import Literal

import redis
from pydantic import BaseModel
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.db.session import get_session_factory


class HealthStatus(BaseModel):
    """Health check response."""

    status: Literal["ok", "down"]
    checks: dict[str, Literal["ok", "down"]]


async def get_health() -> HealthStatus:
    """
    Check health of core infrastructure components.

    Checks:
    - Database: Attempts to execute SELECT 1
    - Redis: Attempts to PING

    Returns:
        HealthStatus with overall status and individual check results
    """
    checks: dict[str, Literal["ok", "down"]] = {}

    # Check database
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "down"

    # Check Redis
    try:
        settings = get_settings()
        redis_client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url, decode_responses=True
        )
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"

    # Overall status - down if any check is down
    overall_status: Literal["ok", "down"] = (
        "ok" if all(status == "ok" for status in checks.values()) else "down"
    )

    return HealthStatus(status=overall_status, checks=checks)
