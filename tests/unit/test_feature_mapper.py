"""Tests for the feature mapper module."""

from datetime import UTC, date, datetime, time

import pytest

from backend.app.adapters.feature_mapper import (
    map_attraction_to_features,
    map_flight_to_features,
    map_fx_to_features,
    map_lodging_to_features,
    map_tool_result_to_features,
    map_transit_to_features,
    map_weather_to_features,
)
from backend.app.models.common import Geo, Provenance, Tier, TimeWindow, TransitMode
from backend.app.models.plan import ChoiceFeatures
from backend.app.models.tool_results import (
    Attraction,
    FlightOption,
    FxRate,
    Lodging,
    TransitLeg,
    WeatherDay,
    Window,
)


@pytest.fixture
def sample_provenance() -> Provenance:
    """Sample provenance for testing."""
    return Provenance(
        source="fixture",
        ref_id="test-ref",
        fetched_at=datetime.now(UTC),
        cache_hit=False,
        response_digest="abc123",
    )


def test_map_flight_to_features(sample_provenance: Provenance) -> None:
    """Test mapping FlightOption to ChoiceFeatures."""
    flight = FlightOption(
        flight_id="FL123",
        origin="CDG",
        dest="JFK",
        departure=datetime.now(UTC),
        arrival=datetime.now(UTC),
        duration_seconds=28800,  # 8 hours
        price_usd_cents=50000,  # $500
        overnight=False,
        provenance=sample_provenance,
    )

    features = map_flight_to_features(flight)

    assert features.cost_usd_cents == 50000
    assert features.travel_seconds == 28800
    assert features.indoor is None  # Flights don't have indoor status
    assert features.themes is None


def test_map_lodging_to_features(sample_provenance: Provenance) -> None:
    """Test mapping Lodging to ChoiceFeatures."""
    lodging = Lodging(
        lodging_id="LODGE123",
        name="Grand Hotel",
        geo=Geo(lat=48.8566, lon=2.3522),
        checkin_window=TimeWindow(start=time(15, 0), end=time(23, 0)),
        checkout_window=TimeWindow(start=time(7, 0), end=time(11, 0)),
        price_per_night_usd_cents=15000,  # $150/night
        tier=Tier.mid,
        kid_friendly=True,
        provenance=sample_provenance,
    )

    features = map_lodging_to_features(lodging)

    assert features.cost_usd_cents == 15000  # Per night
    assert features.travel_seconds is None
    assert features.indoor is True  # Hotels are always indoor
    assert features.themes is None


def test_map_attraction_to_features_museum(sample_provenance: Provenance) -> None:
    """Test mapping museum Attraction to ChoiceFeatures."""
    attraction = Attraction(
        id="ATTR001",
        name="Art Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=True,
        opening_hours={
            "0": [],  # Monday closed
            "1": [Window(start=datetime.now(UTC), end=datetime.now(UTC))],
        },
        location=Geo(lat=48.8566, lon=2.3522),
        est_price_usd_cents=2000,  # $20
        provenance=sample_provenance,
    )

    features = map_attraction_to_features(attraction)

    assert features.cost_usd_cents == 2000
    assert features.travel_seconds is None
    assert features.indoor is True
    assert features.themes is not None
    assert "art" in features.themes
    assert "culture" in features.themes


def test_map_attraction_to_features_park(sample_provenance: Provenance) -> None:
    """Test mapping park Attraction to ChoiceFeatures."""
    attraction = Attraction(
        id="ATTR002",
        name="City Park",
        venue_type="park",
        indoor=False,
        kid_friendly=True,
        opening_hours={},
        location=Geo(lat=48.8566, lon=2.3522),
        est_price_usd_cents=None,  # Free
        provenance=sample_provenance,
    )

    features = map_attraction_to_features(attraction)

    assert features.cost_usd_cents == 0  # Free attractions map to 0
    assert features.indoor is False
    assert features.themes is not None
    assert "outdoor" in features.themes
    assert "nature" in features.themes


def test_map_attraction_to_features_tri_state(sample_provenance: Provenance) -> None:
    """Test that tri-state indoor field is preserved."""
    attraction = Attraction(
        id="ATTR003",
        name="Unknown Venue",
        venue_type="other",
        indoor=None,  # Unknown
        kid_friendly=None,  # Unknown
        opening_hours={},
        location=Geo(lat=48.8566, lon=2.3522),
        provenance=sample_provenance,
    )

    features = map_attraction_to_features(attraction)

    assert features.indoor is None  # Tri-state preserved


def test_map_transit_to_features(sample_provenance: Provenance) -> None:
    """Test mapping TransitLeg to ChoiceFeatures."""
    transit = TransitLeg(
        mode=TransitMode.metro,
        from_geo=Geo(lat=48.8566, lon=2.3522),
        to_geo=Geo(lat=48.8606, lon=2.3376),
        duration_seconds=600,  # 10 minutes
        last_departure=time(23, 30),
        provenance=sample_provenance,
    )

    features = map_transit_to_features(transit)

    assert features.cost_usd_cents == 200  # Metro costs $2
    assert features.travel_seconds == 600
    assert features.indoor is None
    assert features.themes is None


def test_map_transit_to_features_walk(sample_provenance: Provenance) -> None:
    """Test that walking has zero cost."""
    transit = TransitLeg(
        mode=TransitMode.walk,
        from_geo=Geo(lat=48.8566, lon=2.3522),
        to_geo=Geo(lat=48.8606, lon=2.3376),
        duration_seconds=1200,  # 20 minutes
        last_departure=None,
        provenance=sample_provenance,
    )

    features = map_transit_to_features(transit)

    assert features.cost_usd_cents == 0  # Walking is free


def test_map_weather_to_features(sample_provenance: Provenance) -> None:
    """Test mapping WeatherDay to ChoiceFeatures (not a real choice)."""
    weather = WeatherDay(
        forecast_date=date.today(),
        precip_prob=0.6,
        wind_kmh=25.0,
        temp_c_high=22.0,
        temp_c_low=15.0,
        provenance=sample_provenance,
    )

    features = map_weather_to_features(weather)

    # Weather isn't a choice, so all fields should be zero/None
    assert features.cost_usd_cents == 0
    assert features.travel_seconds is None
    assert features.indoor is None
    assert features.themes is None


def test_map_fx_to_features(sample_provenance: Provenance) -> None:
    """Test mapping FxRate to ChoiceFeatures (not a real choice)."""
    fx_rate = FxRate(
        rate=1.08,
        as_of=date.today(),
        provenance=sample_provenance,
    )

    features = map_fx_to_features(fx_rate)

    # FX isn't a choice, so all fields should be zero/None
    assert features.cost_usd_cents == 0
    assert features.travel_seconds is None
    assert features.indoor is None
    assert features.themes is None


def test_map_tool_result_to_features_dispatch(sample_provenance: Provenance) -> None:
    """Test that the dispatch function correctly routes to type-specific mappers."""
    flight = FlightOption(
        flight_id="FL123",
        origin="CDG",
        dest="JFK",
        departure=datetime.now(UTC),
        arrival=datetime.now(UTC),
        duration_seconds=28800,
        price_usd_cents=50000,
        overnight=False,
        provenance=sample_provenance,
    )

    features = map_tool_result_to_features(flight)
    assert isinstance(features, ChoiceFeatures)
    assert features.cost_usd_cents == 50000


def test_map_tool_result_to_features_unknown_type() -> None:
    """Test that unknown types raise TypeError."""
    with pytest.raises(TypeError, match="Unknown tool result type"):
        map_tool_result_to_features("not a tool result")  # type: ignore


def test_feature_mapper_is_deterministic(sample_provenance: Provenance) -> None:
    """Test that feature mapper is deterministic (same input -> same output)."""
    flight = FlightOption(
        flight_id="FL123",
        origin="CDG",
        dest="JFK",
        departure=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
        duration_seconds=28800,
        price_usd_cents=50000,
        overnight=False,
        provenance=sample_provenance,
    )

    features1 = map_flight_to_features(flight)
    features2 = map_flight_to_features(flight)

    assert features1 == features2
    assert features1.model_dump() == features2.model_dump()


def test_feature_mapper_no_io_operations(sample_provenance: Provenance) -> None:
    """Test that feature mapper doesn't perform I/O (pure function)."""
    # This test verifies that mapping is fast (< 1ms) which implies no I/O
    import time

    flight = FlightOption(
        flight_id="FL123",
        origin="CDG",
        dest="JFK",
        departure=datetime.now(UTC),
        arrival=datetime.now(UTC),
        duration_seconds=28800,
        price_usd_cents=50000,
        overnight=False,
        provenance=sample_provenance,
    )

    start = time.time()
    for _ in range(1000):
        map_flight_to_features(flight)
    elapsed = time.time() - start

    # 1000 iterations should complete in < 100ms (pure computation)
    assert elapsed < 0.1, f"Feature mapping too slow: {elapsed}s for 1000 iterations"
