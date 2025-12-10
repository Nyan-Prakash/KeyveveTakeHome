"""Tests for plan API endpoints (PR4).

These are simplified unit tests that verify key behaviors without full DB setup.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_sse_requires_bearer_token():
    """Test that SSE endpoint requires Bearer token."""
    app = create_app()
    client = TestClient(app)

    run_id = uuid4()

    # Try to access SSE without auth
    response = client.get(f"/plan/{run_id}/stream")
    assert response.status_code == 403  # Forbidden (no credentials)


def test_sse_invalid_token_format():
    """Test that SSE endpoint rejects invalid token formats."""
    app = create_app()
    client = TestClient(app)

    run_id = uuid4()

    # Try with empty/whitespace token
    response = client.get(
        f"/plan/{run_id}/stream", headers={"Authorization": "Bearer "}
    )
    # HTTPBearer can return 401 or 403 for invalid credentials
    assert response.status_code in (401, 403)


def test_post_plan_requires_auth():
    """Test that POST /plan requires authentication."""
    app = create_app()
    client = TestClient(app)

    # Try without auth
    response = client.post(
        "/plan",
        json={
            "city": "Paris",
            "date_window": {
                "start": "2025-06-01",
                "end": "2025-06-10",
                "tz": "Europe/Paris",
            },
            "budget_usd_cents": 500000,
            "airports": ["CDG"],
            "prefs": {
                "kid_friendly": False,
                "themes": [],
                "avoid_overnight": False,
                "locked_slots": [],
            },
        },
    )
    assert response.status_code == 403  # Forbidden


@pytest.mark.integration
def test_auth_stub_returns_fixed_user():
    """Test that auth stub returns fixed test user for any valid token."""
    from fastapi.security import HTTPAuthorizationCredentials

    from backend.app.api.auth import get_current_user

    # Any non-empty token should work with stub
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
    user = get_current_user(creds)

    # Stub should return fixed UUIDs
    assert str(user.org_id) == "00000000-0000-0000-0000-000000000001"
    assert str(user.user_id) == "00000000-0000-0000-0000-000000000002"
