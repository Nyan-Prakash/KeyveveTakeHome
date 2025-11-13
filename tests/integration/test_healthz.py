"""Integration tests for /healthz endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.main import app, get_db_session, get_settings_dependency


@pytest.fixture
def test_settings():
    """Create test settings."""
    settings = Settings()
    settings.postgres_url = "sqlite:///:memory:"  # Use in-memory SQLite for tests
    settings.healthcheck_url = "https://www.google.com"
    return settings


@pytest.fixture
def test_engine(test_settings):
    """Create test database engine."""
    engine = create_engine(test_settings.postgres_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    """Create test session factory."""
    return sessionmaker(bind=test_engine)


@pytest.fixture
def test_client(test_settings, test_session_factory):
    """Create test client with dependency overrides."""

    def override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_settings_dependency] = override_get_settings

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_healthz_success(test_client, test_session_factory):
    """Test healthz endpoint returns 200 when all checks pass."""
    # Mock outbound check to succeed
    with patch("backend.app.main.check_outbound") as mock_outbound:
        mock_outbound.return_value = (True, "ok")

        response = test_client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert data["outbound"] == "ok"


def test_healthz_db_failure(test_client):
    """Test healthz endpoint returns 503 when database check fails."""
    # Mock database check to fail
    with patch("backend.app.main.check_database") as mock_db:
        with patch("backend.app.main.check_outbound") as mock_outbound:
            mock_db.return_value = (False, "error")
            mock_outbound.return_value = (True, "ok")

            response = test_client.get("/healthz")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["db"] == "error"
            assert data["outbound"] == "ok"


def test_healthz_outbound_failure(test_client):
    """Test healthz endpoint returns 503 when outbound check fails."""
    with patch("backend.app.main.check_outbound") as mock_outbound:
        mock_outbound.return_value = (False, "error")

        response = test_client.get("/healthz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["db"] == "ok"  # DB should still be ok
        assert data["outbound"] == "error"


def test_healthz_all_failures(test_client):
    """Test healthz endpoint returns 503 when all checks fail."""
    with patch("backend.app.main.check_database") as mock_db:
        with patch("backend.app.main.check_outbound") as mock_outbound:
            mock_db.return_value = (False, "error")
            mock_outbound.return_value = (False, "error")

            response = test_client.get("/healthz")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["db"] == "error"
            assert data["outbound"] == "error"


def test_check_database_success(test_session_factory):
    """Test that check_database succeeds with valid session."""
    from backend.app.api.health import check_database

    session = test_session_factory()
    try:
        ok, status = check_database(session)
        assert ok is True
        assert status == "ok"
    finally:
        session.close()


def test_check_database_failure():
    """Test that check_database fails with broken session."""
    from backend.app.api.health import check_database

    # Create a mock session that raises an exception
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("Database connection failed")

    ok, status = check_database(mock_session)
    assert ok is False
    assert status == "error"


def test_check_outbound_success():
    """Test that check_outbound succeeds with reachable URL."""
    from backend.app.api.health import check_outbound

    with patch("backend.app.api.health.httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client.head.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        ok, status = check_outbound("https://www.google.com")
        assert ok is True
        assert status == "ok"


def test_check_outbound_failure():
    """Test that check_outbound fails with unreachable URL."""
    from backend.app.api.health import check_outbound

    with patch("backend.app.api.health.httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.head.side_effect = Exception("Connection failed")
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        ok, status = check_outbound("https://invalid-url-that-does-not-exist.com")
        assert ok is False
        assert status == "error"


def test_check_outbound_timeout():
    """Test that check_outbound respects timeout."""
    from backend.app.api.health import check_outbound

    with patch("backend.app.api.health.httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.head.side_effect = Exception("Timeout")
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        ok, status = check_outbound("https://slow-site.com", timeout_seconds=0.1)
        assert ok is False
        assert status == "error"
