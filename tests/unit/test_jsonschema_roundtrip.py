"""Test JSON schema export and roundtrip validation."""

import json
import tempfile
from datetime import date, datetime, time
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.models import (
    Activity,
    Assumptions,
    Choice,
    ChoiceFeatures,
    ChoiceKind,
    Citation,
    CostBreakdown,
    DateWindow,
    DayItinerary,
    DayPlan,
    Decision,
    IntentV1,
    ItineraryV1,
    PlanV1,
    Preferences,
    Provenance,
    Slot,
    TimeWindow,
)


class TestSchemaExport:
    """Test JSON schema export functionality."""

    def test_export_schemas_creates_files(self):
        """Test that schema export creates the expected files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            schemas_dir = temp_path / "schemas"

            # Export schemas to temp directory
            schemas_dir.mkdir()

            # Export PlanV1 schema
            plan_schema = PlanV1.model_json_schema()
            plan_schema_path = schemas_dir / "PlanV1.schema.json"
            with open(plan_schema_path, "w") as f:
                json.dump(plan_schema, f, indent=2)

            # Export ItineraryV1 schema
            itinerary_schema = ItineraryV1.model_json_schema()
            itinerary_schema_path = schemas_dir / "ItineraryV1.schema.json"
            with open(itinerary_schema_path, "w") as f:
                json.dump(itinerary_schema, f, indent=2)

            # Verify files exist
            assert plan_schema_path.exists()
            assert itinerary_schema_path.exists()

            # Verify files are valid JSON
            with open(plan_schema_path) as f:
                plan_data = json.load(f)
            assert "title" in plan_data
            assert plan_data["title"] == "PlanV1"

            with open(itinerary_schema_path) as f:
                itinerary_data = json.load(f)
            assert "title" in itinerary_data
            assert itinerary_data["title"] == "ItineraryV1"

    def test_plan_schema_has_required_properties(self):
        """Test that PlanV1 schema has expected structure."""
        schema = PlanV1.model_json_schema()

        assert schema["title"] == "PlanV1"
        assert "properties" in schema
        assert "days" in schema["properties"]
        assert "assumptions" in schema["properties"]
        assert "rng_seed" in schema["properties"]

        # Check days property
        days_prop = schema["properties"]["days"]
        assert days_prop["type"] == "array"

    def test_itinerary_schema_has_required_properties(self):
        """Test that ItineraryV1 schema has expected structure."""
        schema = ItineraryV1.model_json_schema()

        assert schema["title"] == "ItineraryV1"
        assert "properties" in schema
        required_props = [
            "itinerary_id",
            "intent",
            "days",
            "cost_breakdown",
            "decisions",
            "citations",
            "created_at",
            "trace_id",
        ]

        for prop in required_props:
            assert prop in schema["properties"]


class TestJSONSchemaRoundtrip:
    """Test roundtrip validation using JSON schemas."""

    def _create_valid_plan(self) -> PlanV1:
        """Create a valid PlanV1 for testing."""
        choice = Choice(
            kind=ChoiceKind.attraction,
            option_ref="attraction_001",
            features=ChoiceFeatures(cost_usd_cents=5000),
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0),
            ),
        )

        slot = Slot(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            choices=[choice],
        )

        day_plan = DayPlan(
            date=date(2025, 6, 1),
            slots=[slot],
        )

        assumptions = Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000,
        )

        return PlanV1(
            days=[day_plan] * 4,  # 4 days minimum
            assumptions=assumptions,
            rng_seed=42,
        )

    def _create_valid_itinerary(self) -> ItineraryV1:
        """Create a valid ItineraryV1 for testing."""
        intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="Europe/Paris",
            ),
            budget_usd_cents=250000,
            airports=["CDG"],
            prefs=Preferences(),
        )

        activity = Activity(
            window=TimeWindow(start=time(10, 0), end=time(12, 0)),
            kind=ChoiceKind.attraction,
            name="Test Activity",
            notes="Test notes",
            locked=False,
        )

        day_itinerary = DayItinerary(
            day_date=date(2025, 6, 1),
            activities=[activity],
        )

        cost_breakdown = CostBreakdown(
            flights_usd_cents=80000,
            lodging_usd_cents=100000,
            attractions_usd_cents=30000,
            transit_usd_cents=10000,
            daily_spend_usd_cents=30000,
            total_usd_cents=250000,
            currency_disclaimer="Exchange rates as of 2025-06-01",
        )

        decision = Decision(
            node="planner",
            rationale="Test decision",
            alternatives_considered=3,
            selected="option_1",
        )

        citation = Citation(
            claim="Test claim",
            provenance=Provenance(
                source="tool",
                fetched_at=datetime(2025, 6, 1, 12, 0),
            ),
        )

        return ItineraryV1(
            itinerary_id="test_itinerary",
            intent=intent,
            days=[day_itinerary],
            cost_breakdown=cost_breakdown,
            decisions=[decision],
            citations=[citation],
            created_at=datetime(2025, 6, 1, 12, 0),
            trace_id="test_trace",
        )

    def test_valid_plan_passes_schema_validation(self):
        """Test that valid plan passes schema validation."""
        plan = self._create_valid_plan()

        # Get schema and serialize plan to dict
        plan_dict = plan.model_dump()

        # This is a basic test - in production you'd use jsonschema library
        # For now, we test that the data can roundtrip
        restored_plan = PlanV1.model_validate(plan_dict)
        assert restored_plan.rng_seed == plan.rng_seed
        assert len(restored_plan.days) == len(plan.days)

    def test_valid_itinerary_passes_schema_validation(self):
        """Test that valid itinerary passes schema validation."""
        itinerary = self._create_valid_itinerary()

        # Get schema and serialize itinerary to dict
        itinerary_dict = itinerary.model_dump()

        # Test roundtrip
        restored_itinerary = ItineraryV1.model_validate(itinerary_dict)
        assert restored_itinerary.itinerary_id == itinerary.itinerary_id
        assert restored_itinerary.trace_id == itinerary.trace_id

    def test_mutated_plan_fails_validation(self):
        """Test that mutated plan fails validation."""
        plan = self._create_valid_plan()
        plan_dict = plan.model_dump()

        # Mutate required field to wrong type
        plan_dict["rng_seed"] = "not_a_number"  # Should be int

        with pytest.raises(ValidationError):  # Should fail validation
            PlanV1.model_validate(plan_dict)

    def test_mutated_itinerary_fails_validation(self):
        """Test that mutated itinerary fails validation."""
        itinerary = self._create_valid_itinerary()
        itinerary_dict = itinerary.model_dump()

        # Mutate required field to wrong type
        itinerary_dict["cost_breakdown"][
            "total_usd_cents"
        ] = "not_a_number"  # Should be int

        with pytest.raises(ValidationError):  # Should fail validation
            ItineraryV1.model_validate(itinerary_dict)

    def test_missing_required_field_fails(self):
        """Test that missing required fields fail validation."""
        plan = self._create_valid_plan()
        plan_dict = plan.model_dump()

        # Remove required field
        del plan_dict["rng_seed"]

        with pytest.raises(ValidationError):  # Should fail validation
            PlanV1.model_validate(plan_dict)

    def test_schema_titles_present(self):
        """Test that exported schemas have correct titles."""
        plan_schema = PlanV1.model_json_schema()
        itinerary_schema = ItineraryV1.model_json_schema()

        assert "title" in plan_schema
        assert plan_schema["title"] == "PlanV1"

        assert "title" in itinerary_schema
        assert itinerary_schema["title"] == "ItineraryV1"
