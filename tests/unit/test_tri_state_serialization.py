"""Test tri-state boolean serialization for indoor/kid_friendly fields."""

import json
from datetime import datetime

from backend.app.models import (
    Attraction,
    ChoiceFeatures,
    Geo,
    Provenance,
    Window,
)


class TestAttractionTriState:
    """Test Attraction model tri-state serialization."""

    def _create_base_attraction(
        self,
        indoor: bool | None = None,
        kid_friendly: bool | None = None,
    ) -> Attraction:
        """Helper to create attraction with tri-state values."""
        provenance = Provenance(
            source="tool",
            fetched_at=datetime(2025, 6, 1, 12, 0, 0),
        )

        return Attraction(
            id="test_attraction",
            name="Test Attraction",
            venue_type="museum",
            indoor=indoor,
            kid_friendly=kid_friendly,
            opening_hours={
                "0": [
                    Window(
                        start=datetime(2025, 6, 1, 9, 0, 0),
                        end=datetime(2025, 6, 1, 17, 0, 0),
                    )
                ],
                "1": [],
                "2": [],
                "3": [],
                "4": [],
                "5": [],
                "6": [],
            },
            location=Geo(lat=48.8566, lon=2.3522),
            provenance=provenance,
        )

    def test_indoor_true_roundtrip(self):
        """Test indoor=True roundtrip serialization."""
        attraction = self._create_base_attraction(indoor=True)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains correct value
        assert json_data["indoor"] is True

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.indoor is True

    def test_indoor_false_roundtrip(self):
        """Test indoor=False roundtrip serialization."""
        attraction = self._create_base_attraction(indoor=False)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains correct value
        assert json_data["indoor"] is False

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.indoor is False

    def test_indoor_none_roundtrip(self):
        """Test indoor=None roundtrip serialization."""
        attraction = self._create_base_attraction(indoor=None)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains null
        assert json_data["indoor"] is None

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.indoor is None

    def test_kid_friendly_true_roundtrip(self):
        """Test kid_friendly=True roundtrip serialization."""
        attraction = self._create_base_attraction(kid_friendly=True)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains correct value
        assert json_data["kid_friendly"] is True

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.kid_friendly is True

    def test_kid_friendly_false_roundtrip(self):
        """Test kid_friendly=False roundtrip serialization."""
        attraction = self._create_base_attraction(kid_friendly=False)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains correct value
        assert json_data["kid_friendly"] is False

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.kid_friendly is False

    def test_kid_friendly_none_roundtrip(self):
        """Test kid_friendly=None roundtrip serialization."""
        attraction = self._create_base_attraction(kid_friendly=None)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON contains null
        assert json_data["kid_friendly"] is None

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.kid_friendly is None

    def test_both_tri_state_roundtrip(self):
        """Test both tri-state fields together."""
        attraction = self._create_base_attraction(indoor=True, kid_friendly=None)

        # Serialize to JSON
        json_str = attraction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON values
        assert json_data["indoor"] is True
        assert json_data["kid_friendly"] is None

        # Deserialize back
        restored = Attraction.model_validate(json_data)
        assert restored.indoor is True
        assert restored.kid_friendly is None


class TestChoiceFeaturesTriState:
    """Test ChoiceFeatures tri-state serialization."""

    def test_choice_features_indoor_true_roundtrip(self):
        """Test ChoiceFeatures indoor=True roundtrip."""
        features = ChoiceFeatures(
            cost_usd_cents=5000,
            indoor=True,
        )

        # Serialize to JSON
        json_str = features.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON value
        assert json_data["indoor"] is True

        # Deserialize back
        restored = ChoiceFeatures.model_validate(json_data)
        assert restored.indoor is True

    def test_choice_features_indoor_false_roundtrip(self):
        """Test ChoiceFeatures indoor=False roundtrip."""
        features = ChoiceFeatures(
            cost_usd_cents=5000,
            indoor=False,
        )

        # Serialize to JSON
        json_str = features.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON value
        assert json_data["indoor"] is False

        # Deserialize back
        restored = ChoiceFeatures.model_validate(json_data)
        assert restored.indoor is False

    def test_choice_features_indoor_none_roundtrip(self):
        """Test ChoiceFeatures indoor=None roundtrip."""
        features = ChoiceFeatures(
            cost_usd_cents=5000,
            indoor=None,
        )

        # Serialize to JSON
        json_str = features.model_dump_json()
        json_data = json.loads(json_str)

        # Verify JSON value
        assert json_data["indoor"] is None

        # Deserialize back
        restored = ChoiceFeatures.model_validate(json_data)
        assert restored.indoor is None

    def test_choice_features_missing_indoor_defaults_none(self):
        """Test ChoiceFeatures with missing indoor field defaults to None."""
        # Create minimal features without indoor field
        json_data = {"cost_usd_cents": 5000}

        restored = ChoiceFeatures.model_validate(json_data)
        assert restored.indoor is None
        assert restored.cost_usd_cents == 5000


class TestTriStateEdgeCases:
    """Test edge cases for tri-state serialization."""

    def test_explicit_null_in_json(self):
        """Test that explicit null in JSON deserializes to None."""
        json_data = {
            "id": "test",
            "name": "Test",
            "venue_type": "museum",
            "indoor": None,  # Explicit None/null
            "kid_friendly": None,
            "opening_hours": {str(i): [] for i in range(7)},
            "location": {"lat": 48.8566, "lon": 2.3522},
            "provenance": {
                "source": "tool",
                "fetched_at": "2025-06-01T12:00:00",
            },
        }

        attraction = Attraction.model_validate(json_data)
        assert attraction.indoor is None
        assert attraction.kid_friendly is None

    def test_missing_optional_tri_state_fields(self):
        """Test that missing optional tri-state fields default to None."""
        json_data = {
            "id": "test",
            "name": "Test",
            "venue_type": "museum",
            # indoor and kid_friendly are missing
            "opening_hours": {str(i): [] for i in range(7)},
            "location": {"lat": 48.8566, "lon": 2.3522},
            "provenance": {
                "source": "tool",
                "fetched_at": "2025-06-01T12:00:00",
            },
        }

        attraction = Attraction.model_validate(json_data)
        assert attraction.indoor is None
        assert attraction.kid_friendly is None
