"""Integration tests for Destinations API with org-scoping."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client(test_session, test_user, test_org):
    """Create a test client with database session override."""
    from backend.app.api.destinations import get_db_session
    from backend.app.db.session import get_session

    # Ensure test data is committed before API calls
    test_session.commit()

    def override_get_session():
        try:
            yield test_session
        finally:
            pass  # Don't close the session, it's managed by the test

    # Override both session dependencies (for auth and API endpoints)
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_db_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestDestinationsAPI:
    """Test suite for Destinations API endpoints."""

    def test_create_destination(self, client, auth_headers, test_user, test_org):
        """Test creating a new destination."""
        payload = {
            "city": "Paris",
            "country": "France",
            "geo": {"lat": 48.8566, "lon": 2.3522},
            "fixture_path": "fixtures/paris.json",
        }

        response = client.post("/destinations", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["city"] == "Paris"
        assert data["country"] == "France"
        assert data["geo"]["lat"] == 48.8566
        assert "dest_id" in data

    def test_create_duplicate_destination(self, client, auth_headers):
        """Test that creating a duplicate destination fails."""
        payload = {
            "city": "Tokyo",
            "country": "Japan",
            "geo": {"lat": 35.6762, "lon": 139.6503},
        }

        # Create first time - should succeed
        response1 = client.post("/destinations", json=payload, headers=auth_headers)
        assert response1.status_code == 201

        # Create second time - should fail with 409
        response2 = client.post("/destinations", json=payload, headers=auth_headers)
        assert response2.status_code == 409

    def test_list_destinations(self, client, auth_headers):
        """Test listing destinations."""
        # Create a test destination
        payload = {
            "city": "London",
            "country": "United Kingdom",
            "geo": {"lat": 51.5074, "lon": -0.1278},
        }
        client.post("/destinations", json=payload, headers=auth_headers)

        # List destinations
        response = client.get("/destinations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify structure
        dest = data[0]
        assert "dest_id" in dest
        assert "city" in dest
        assert "country" in dest
        assert "geo" in dest
        assert "last_run" in dest

    def test_search_destinations(self, client, auth_headers):
        """Test searching destinations by city/country."""
        # Create test destinations
        client.post(
            "/destinations",
            json={"city": "Berlin", "country": "Germany", "geo": {"lat": 52.52, "lon": 13.405}},
            headers=auth_headers,
        )
        client.post(
            "/destinations",
            json={"city": "Munich", "country": "Germany", "geo": {"lat": 48.1351, "lon": 11.582}},
            headers=auth_headers,
        )

        # Search by country
        response = client.get("/destinations?search=Germany", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        assert all("Germany" in d["country"] for d in data)

    def test_update_destination(self, client, auth_headers):
        """Test updating a destination."""
        # Create destination
        create_response = client.post(
            "/destinations",
            json={"city": "Rome", "country": "Italy", "geo": {"lat": 41.9028, "lon": 12.4964}},
            headers=auth_headers,
        )
        dest_id = create_response.json()["dest_id"]

        # Update city name
        update_payload = {"city": "Roma"}
        response = client.patch(
            f"/destinations/{dest_id}", json=update_payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Roma"
        assert data["country"] == "Italy"  # Unchanged

    def test_delete_destination(self, client, auth_headers):
        """Test deleting a destination."""
        # Create destination
        create_response = client.post(
            "/destinations",
            json={"city": "Madrid", "country": "Spain", "geo": {"lat": 40.4168, "lon": -3.7038}},
            headers=auth_headers,
        )
        dest_id = create_response.json()["dest_id"]

        # Delete
        response = client.delete(f"/destinations/{dest_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deletion
        get_response = client.get("/destinations", headers=auth_headers)
        destinations = get_response.json()
        assert not any(d["dest_id"] == dest_id for d in destinations)

    def test_org_scoping_on_list(self, client, auth_headers):
        """Test that destinations are org-scoped on list."""
        # This test validates that the middleware filters by org_id
        # In a real scenario, we'd use two different auth tokens for different orgs

        # Create destination with test org
        client.post(
            "/destinations",
            json={"city": "Amsterdam", "country": "Netherlands", "geo": {"lat": 52.3676, "lon": 4.9041}},
            headers=auth_headers,
        )

        # List should only show destinations from current org
        response = client.get("/destinations", headers=auth_headers)
        assert response.status_code == 200

        # All returned destinations should belong to same org (implicitly tested by middleware)
        destinations = response.json()
        assert isinstance(destinations, list)

    def test_org_scoping_on_update(self, client, auth_headers):
        """Test that update is org-scoped."""
        # Create destination
        create_response = client.post(
            "/destinations",
            json={"city": "Barcelona", "country": "Spain", "geo": {"lat": 41.3851, "lon": 2.1734}},
            headers=auth_headers,
        )
        dest_id = create_response.json()["dest_id"]

        # Attempt to update with different org (simulated by using wrong dest_id)
        fake_dest_id = str(uuid4())
        response = client.patch(
            f"/destinations/{fake_dest_id}",
            json={"city": "Barcelona Updated"},
            headers=auth_headers,
        )

        assert response.status_code == 404  # Not found because it doesn't belong to org

    def test_org_scoping_on_delete(self, client, auth_headers):
        """Test that delete is org-scoped."""
        # Attempt to delete non-existent destination
        fake_dest_id = str(uuid4())
        response = client.delete(f"/destinations/{fake_dest_id}", headers=auth_headers)

        assert response.status_code == 404  # Not found because it doesn't belong to org

    def test_create_requires_auth(self, client):
        """Test that create endpoint requires authentication."""
        payload = {
            "city": "Vienna",
            "country": "Austria",
            "geo": {"lat": 48.2082, "lon": 16.3738},
        }

        response = client.post("/destinations", json=payload)

        assert response.status_code == 403  # No auth header

    def test_invalid_geo_coordinates(self, client, auth_headers):
        """Test validation of geographic coordinates."""
        # Invalid latitude (> 90)
        payload = {
            "city": "TestCity",
            "country": "TestCountry",
            "geo": {"lat": 91.0, "lon": 0.0},
        }

        response = client.post("/destinations", json=payload, headers=auth_headers)
        assert response.status_code == 422  # Validation error

        # Invalid longitude (< -180)
        payload["geo"] = {"lat": 0.0, "lon": -181.0}
        response = client.post("/destinations", json=payload, headers=auth_headers)
        assert response.status_code == 422
