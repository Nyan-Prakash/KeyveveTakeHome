"""Unit tests for health check endpoint."""

import asyncio
from unittest.mock import MagicMock, patch

from backend.app.api.health import get_health


def test_healthz_ok_when_db_and_redis_ok() -> None:
    """Test health check returns ok when all services are healthy."""
    # Mock successful DB query
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute = MagicMock()

    mock_factory = MagicMock(return_value=mock_session)

    # Mock successful Redis ping
    mock_redis = MagicMock()
    mock_redis.ping = MagicMock()

    with (
        patch("backend.app.api.health.get_session_factory", return_value=mock_factory),
        patch("backend.app.api.health.redis.from_url", return_value=mock_redis),
    ):
        result = asyncio.run(get_health())

    assert result.status == "ok"
    assert result.checks["db"] == "ok"
    assert result.checks["redis"] == "ok"


def test_healthz_down_when_db_fails() -> None:
    """Test health check returns down when DB fails."""
    # Mock failing DB query
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute = MagicMock(side_effect=Exception("DB connection failed"))

    mock_factory = MagicMock(return_value=mock_session)

    # Mock successful Redis ping
    mock_redis = MagicMock()
    mock_redis.ping = MagicMock()

    with (
        patch("backend.app.api.health.get_session_factory", return_value=mock_factory),
        patch("backend.app.api.health.redis.from_url", return_value=mock_redis),
    ):
        result = asyncio.run(get_health())

    assert result.status == "down"
    assert result.checks["db"] == "down"
    assert result.checks["redis"] == "ok"


def test_healthz_down_when_redis_fails() -> None:
    """Test health check returns down when Redis fails."""
    # Mock successful DB query
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute = MagicMock()

    mock_factory = MagicMock(return_value=mock_session)

    # Mock failing Redis ping
    mock_redis = MagicMock()
    mock_redis.ping = MagicMock(side_effect=Exception("Redis connection failed"))

    with (
        patch("backend.app.api.health.get_session_factory", return_value=mock_factory),
        patch("backend.app.api.health.redis.from_url", return_value=mock_redis),
    ):
        result = asyncio.run(get_health())

    assert result.status == "down"
    assert result.checks["db"] == "ok"
    assert result.checks["redis"] == "down"


def test_healthz_down_when_both_fail() -> None:
    """Test health check returns down when both services fail."""
    # Mock failing DB query
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute = MagicMock(side_effect=Exception("DB failed"))

    mock_factory = MagicMock(return_value=mock_session)

    # Mock failing Redis ping
    mock_redis = MagicMock()
    mock_redis.ping = MagicMock(side_effect=Exception("Redis failed"))

    with (
        patch("backend.app.api.health.get_session_factory", return_value=mock_factory),
        patch("backend.app.api.health.redis.from_url", return_value=mock_redis),
    ):
        result = asyncio.run(get_health())

    assert result.status == "down"
    assert result.checks["db"] == "down"
    assert result.checks["redis"] == "down"
