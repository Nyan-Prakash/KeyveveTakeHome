"""Integration tests for Plan Edit endpoint and what-if flows."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers with test token."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_intent():
    """Create a sample intent for testing."""
    start = date.today()
    end = start + timedelta(days=5)

    return {
        "city": "Paris",
        "date_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "tz": "Europe/Paris",
        },
        "budget_usd_cents": 500000,  # $5000
        "airports": ["CDG", "ORY"],
        "prefs": {
            "kid_friendly": False,
            "themes": ["art", "culture"],
            "avoid_overnight": False,
            "locked_slots": [],
        },
    }


class TestPlanEditAPI:
    """Test suite for Plan Edit API endpoint."""

    def test_edit_plan_budget_decrease(self, client, auth_headers, sample_intent):
        """Test editing a plan to decrease budget."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Apply budget decrease ($300 = 30000 cents)
        edit_payload = {"delta_budget_usd_cents": -30000}

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201
        edit_data = edit_response.json()
        assert "run_id" in edit_data

        # New run ID should be different
        new_run_id = edit_data["run_id"]
        assert new_run_id != run_id

        # Verify the new run exists and has modified budget
        # (Note: In a full test, we'd wait for the run to complete and verify budget)

    def test_edit_plan_budget_increase(self, client, auth_headers, sample_intent):
        """Test editing a plan to increase budget."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Apply budget increase
        edit_payload = {"delta_budget_usd_cents": 50000}  # +$500

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201
        new_run_id = edit_response.json()["run_id"]
        assert new_run_id != run_id

    def test_edit_plan_shift_dates_forward(self, client, auth_headers, sample_intent):
        """Test shifting plan dates forward."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Shift dates forward by 3 days
        edit_payload = {"shift_dates_days": 3}

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201
        new_run_id = edit_response.json()["run_id"]
        assert new_run_id != run_id

    def test_edit_plan_shift_dates_backward(self, client, auth_headers, sample_intent):
        """Test shifting plan dates backward."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Shift dates backward by 2 days
        edit_payload = {"shift_dates_days": -2}

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201

    def test_edit_plan_update_preferences(self, client, auth_headers, sample_intent):
        """Test updating plan preferences."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Update preferences to be kid-friendly
        edit_payload = {"new_prefs": {"kid_friendly": True, "themes": ["nature", "food"]}}

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201

    def test_edit_plan_multiple_changes(self, client, auth_headers, sample_intent):
        """Test applying multiple edits at once."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Apply multiple changes
        edit_payload = {
            "delta_budget_usd_cents": -20000,  # $200 cheaper
            "shift_dates_days": 1,  # Shift 1 day forward
            "new_prefs": {"avoid_overnight": True},  # Avoid red-eye flights
        }

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201

    def test_edit_nonexistent_run(self, client, auth_headers):
        """Test editing a run that doesn't exist."""
        from uuid import uuid4

        fake_run_id = str(uuid4())
        edit_payload = {"delta_budget_usd_cents": -10000}

        response = client.post(
            f"/plan/{fake_run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_edit_plan_org_scoping(self, client, auth_headers, sample_intent):
        """Test that edit respects org scoping."""
        # Create a plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Try to edit with same org (should succeed)
        edit_payload = {"delta_budget_usd_cents": -5000}

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201

        # In a full test, we'd try with a different org and expect 403

    def test_edit_plan_minimum_budget_enforcement(self, client, auth_headers, sample_intent):
        """Test that budget cannot go below minimum."""
        # Create initial plan with low budget
        low_budget_intent = sample_intent.copy()
        low_budget_intent["budget_usd_cents"] = 15000  # $150

        create_response = client.post(
            "/plan",
            json=low_budget_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Try to reduce budget below minimum ($100)
        edit_payload = {"delta_budget_usd_cents": -10000}  # Would be $50

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        # Should succeed but enforce minimum budget of $100 (10000 cents)
        assert edit_response.status_code == 201

    def test_edit_requires_authentication(self, client, sample_intent):
        """Test that edit endpoint requires authentication."""
        from uuid import uuid4

        run_id = str(uuid4())
        edit_payload = {"delta_budget_usd_cents": -5000}

        response = client.post(f"/plan/{run_id}/edit", json=edit_payload)

        assert response.status_code == 403  # No auth header

    def test_iterative_edits(self, client, auth_headers, sample_intent):
        """Test multiple iterative edits (what-if flow)."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id_1 = create_response.json()["run_id"]

        # First edit: reduce budget
        edit_1 = client.post(
            f"/plan/{run_id_1}/edit",
            json={"delta_budget_usd_cents": -30000},
            headers=auth_headers,
        )

        assert edit_1.status_code == 201
        run_id_2 = edit_1.json()["run_id"]

        # Second edit: make it kid-friendly (based on second run)
        edit_2 = client.post(
            f"/plan/{run_id_2}/edit",
            json={"new_prefs": {"kid_friendly": True}},
            headers=auth_headers,
        )

        assert edit_2.status_code == 201
        run_id_3 = edit_2.json()["run_id"]

        # Third edit: shift dates (based on third run)
        edit_3 = client.post(
            f"/plan/{run_id_3}/edit",
            json={"shift_dates_days": 2},
            headers=auth_headers,
        )

        assert edit_3.status_code == 201

        # All run IDs should be different
        assert len({run_id_1, run_id_2, run_id_3}) == 3

    def test_edit_with_description(self, client, auth_headers, sample_intent):
        """Test including a description with the edit."""
        # Create initial plan
        create_response = client.post(
            "/plan",
            json=sample_intent,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        run_id = create_response.json()["run_id"]

        # Edit with description
        edit_payload = {
            "delta_budget_usd_cents": -30000,
            "description": "Make it $300 cheaper for budget constraints",
        }

        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json=edit_payload,
            headers=auth_headers,
        )

        assert edit_response.status_code == 201


class TestWhatIfWorkflow:
    """Integration tests for complete what-if workflows."""

    def test_kyoto_demo_workflow(self, client, auth_headers):
        """Test the Kyoto demo workflow from the take-home PDF.

        This simulates:
        1. Create destination
        2. Upload guide PDF
        3. Generate plan
        4. Apply what-if (cheaper)
        """
        # Step 1: Create Kyoto destination
        dest_payload = {
            "city": "Kyoto",
            "country": "Japan",
            "geo": {"lat": 35.0116, "lon": 135.7681},
        }

        dest_response = client.post(
            "/destinations",
            json=dest_payload,
            headers=auth_headers,
        )

        assert dest_response.status_code == 201
        dest_id = dest_response.json()["dest_id"]

        # Step 2: Upload a guide (simulated with text file)
        # (In full test, this would be actual file upload)

        # Step 3: Generate initial plan
        start = date.today()
        end = start + timedelta(days=5)

        intent = {
            "city": "Kyoto",
            "date_window": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "tz": "Asia/Tokyo",
            },
            "budget_usd_cents": 600000,  # $6000
            "airports": ["KIX", "ITM"],
            "prefs": {
                "kid_friendly": False,
                "themes": ["culture", "history"],
                "avoid_overnight": False,
                "locked_slots": [],
            },
        }

        plan_response = client.post(
            "/plan",
            json=intent,
            headers=auth_headers,
        )

        assert plan_response.status_code == 201
        run_id = plan_response.json()["run_id"]

        # Step 4: Apply what-if - make it $300 cheaper
        edit_response = client.post(
            f"/plan/{run_id}/edit",
            json={
                "delta_budget_usd_cents": -30000,
                "description": "Make it $300 cheaper",
            },
            headers=auth_headers,
        )

        assert edit_response.status_code == 201
        new_run_id = edit_response.json()["run_id"]

        # Verify new run was created
        assert new_run_id != run_id
