"""Tests for PR5: Adapters and Feature Mapper.

Merge gates:
1. All adapter returns carry provenance (ref_id + source_url)
2. Missing provenance fails validation
3. Cache hit toggles metrics (weather/fx)
4. Forced timeouts trip breaker
5. Feature mapper is pure and deterministic
6. Selector cannot touch raw tool fields (structural)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time
from typing import Any

import pytest

from backend.app.adapters.events import get_events
from backend.app.adapters.flights import get_flights
from backend.app.adapters.fx import get_fx_rate
from backend.app.adapters.lodging import get_lodging
from backend.app.adapters.transit import get_transit_legs
from backend.app.adapters.weather import get_weather_forecast
from backend.app.config import Settings
from backend.app.exec.executor import InMemoryToolCache, ToolExecutor
from backend.app.exec.types import ToolResult
from backend.app.features.mapper import (
    attraction_to_choice,
    flight_to_choice,
    lodging_to_choice,
    to_choice,
    transit_to_choice,
)
from backend.app.metrics.registry import MetricsClient
from backend.app.models.common import Geo, Provenance, TransitMode
from backend.app.models.plan import Choice, ChoiceFeatures
from backend.app.models.tool_results import (
    Attraction,
    FlightOption,
    Lodging,
    TransitLeg,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def metrics() -> MetricsClient:
    """Create MetricsClient for tests."""
    return MetricsClient()


@pytest.fixture
def cache() -> InMemoryToolCache:
    """Create in-memory tool cache."""
    return InMemoryToolCache()


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        weather_api_key="test_api_key",
        weather_ttl_hours=24,
        soft_timeout_s=2.0,
        hard_timeout_s=4.0,
        breaker_failure_threshold=5,
        breaker_timeout_s=60,
    )


@pytest.fixture
def executor(
    metrics: MetricsClient, cache: InMemoryToolCache, settings: Settings
) -> ToolExecutor:
    """Create ToolExecutor for tests."""
    return ToolExecutor(metrics=metrics, cache=cache, settings=settings)


# ============================================================================
# GATE 1 & 2: PROVENANCE VALIDATION
# ============================================================================


def test_all_flight_results_have_provenance(executor: ToolExecutor) -> None:
    """All flight adapter results must have non-empty provenance."""
    flights = get_flights(
        executor=executor,
        origin="SEA",
        destination="LHR",
        departure_date=date(2025, 6, 15),
    )

    assert len(flights) > 0, "Should return at least one flight"

    for flight in flights:
        # Check provenance exists
        assert flight.provenance is not None, "Provenance must be present"

        # Check ref_id is non-empty
        assert flight.provenance.ref_id, "Provenance ref_id must be non-empty"

        # Check source_url is non-empty
        assert flight.provenance.source_url, "Provenance source_url must be non-empty"

        # Check source is valid
        assert flight.provenance.source == "tool", "Source must be 'tool'"


def test_all_lodging_results_have_provenance(executor: ToolExecutor) -> None:
    """All lodging adapter results must have non-empty provenance."""
    lodging = get_lodging(executor=executor, city="london")

    assert len(lodging) > 0, "Should return at least one lodging"

    for lodge in lodging:
        assert lodge.provenance is not None
        assert lodge.provenance.ref_id
        assert lodge.provenance.source_url
        assert lodge.provenance.source == "tool"


def test_all_event_results_have_provenance(executor: ToolExecutor) -> None:
    """All event/attraction adapter results must have non-empty provenance."""
    events = get_events(executor=executor, city="paris")

    assert len(events) > 0, "Should return at least one event"

    for event in events:
        assert event.provenance is not None
        assert event.provenance.ref_id
        assert event.provenance.source_url
        assert event.provenance.source == "tool"


def test_all_transit_results_have_provenance(executor: ToolExecutor) -> None:
    """All transit adapter results must have non-empty provenance."""
    from_geo = Geo(lat=51.5074, lon=-0.1278)
    to_geo = Geo(lat=51.5194, lon=-0.1270)

    transit = get_transit_legs(executor=executor, from_geo=from_geo, to_geo=to_geo)

    assert len(transit) > 0, "Should return at least one transit option"

    for leg in transit:
        assert leg.provenance is not None
        assert leg.provenance.ref_id
        assert leg.provenance.source_url
        assert leg.provenance.source == "tool"


def test_fx_rate_has_provenance(executor: ToolExecutor) -> None:
    """FX rate must have non-empty provenance."""
    fx = get_fx_rate(executor=executor, from_currency="USD", to_currency="EUR")

    assert fx.provenance is not None
    assert fx.provenance.ref_id
    assert fx.provenance.source_url
    assert fx.provenance.source == "tool"


def test_missing_provenance_fails_validation() -> None:
    """Tool objects without provenance should fail validation."""
    # Attempt to create FlightOption without provenance
    with pytest.raises(ValueError, match="provenance"):
        FlightOption(
            flight_id="test-flight",
            origin="SEA",
            dest="LHR",
            departure=datetime.now(UTC),
            arrival=datetime.now(UTC),
            duration_seconds=36000,
            price_usd_cents=85000,
            overnight=True,
            # provenance intentionally missing
        )  # type: ignore[call-arg]


# ============================================================================
# GATE 3: CACHE HIT TOGGLES METRICS
# ============================================================================


def test_weather_cache_hit_increments_metric(
    executor: ToolExecutor,
    metrics: MetricsClient,
    settings: Settings,
) -> None:
    """Weather adapter cache hit should increment cache_hit metric."""
    # Mock the weather API call
    mock_response = {
        "daily": [
            {
                "temp": {"max": 22.0, "min": 12.0},
                "wind_speed": 5.0,
                "pop": 0.2,
            }
        ]
    }

    # Patch the tool to return mock data
    async def mock_weather_tool(args: dict[str, Any]) -> dict[str, Any]:
        return mock_response

    # Replace executor's execute method to use our mock
    original_execute = executor.execute

    def patched_execute(
        tool: Any, name: str, args: dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        # For weather calls, use sync wrapper
        if name == "weather":

            def sync_wrapper(a: dict[str, Any]) -> dict[str, Any]:
                return asyncio.run(mock_weather_tool(a))

            return original_execute(sync_wrapper, name, args, **kwargs)
        return original_execute(tool, name, args, **kwargs)

    executor.execute = patched_execute  # type: ignore[method-assign]

    location = Geo(lat=48.8566, lon=2.3522)
    start = date(2025, 6, 15)
    end = date(2025, 6, 15)

    # First call - should miss cache
    initial_cache_hits = metrics.tool_cache_hits.get("weather", 0)

    result1 = get_weather_forecast(
        executor=executor,
        settings=settings,
        location=location,
        start_date=start,
        end_date=end,
    )

    assert len(result1) > 0
    assert result1[0].provenance.cache_hit is False

    # Second call with identical args - should hit cache
    result2 = get_weather_forecast(
        executor=executor,
        settings=settings,
        location=location,
        start_date=start,
        end_date=end,
    )

    assert len(result2) > 0
    assert result2[0].provenance.cache_hit is True

    # Verify cache hit metric incremented
    final_cache_hits = metrics.tool_cache_hits.get("weather", 0)
    assert final_cache_hits > initial_cache_hits, "Cache hit metric should increment"


def test_fx_cache_hit_increments_metric(
    executor: ToolExecutor,
    metrics: MetricsClient,
) -> None:
    """FX adapter cache hit should increment cache_hit metric."""
    initial_cache_hits = metrics.tool_cache_hits.get("fx", 0)

    # First call - cache miss
    fx1 = get_fx_rate(executor=executor, from_currency="USD", to_currency="EUR")
    assert fx1.provenance.cache_hit is False

    # Second call - cache hit
    fx2 = get_fx_rate(executor=executor, from_currency="USD", to_currency="EUR")
    assert fx2.provenance.cache_hit is True

    # Verify metric incremented
    final_cache_hits = metrics.tool_cache_hits.get("fx", 0)
    assert final_cache_hits > initial_cache_hits


# ============================================================================
# GATE 4: FORCED TIMEOUTS TRIP BREAKER
# ============================================================================


def test_forced_timeouts_open_breaker(
    metrics: MetricsClient,
    cache: InMemoryToolCache,
    settings: Settings,
) -> None:
    """Repeated timeouts should open the circuit breaker."""
    from backend.app.exec.types import BreakerPolicy, CachePolicy

    executor = ToolExecutor(metrics=metrics, cache=cache, settings=settings)

    # Create a tool that always times out
    async def timeout_tool(args: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        await asyncio.sleep(10)  # Exceeds hard timeout (4s)
        return {}

    # Call the tool repeatedly to trigger breaker
    failure_count = 0
    breaker_opened = False

    for _ in range(10):
        result = executor.execute(
            tool=timeout_tool,
            name="test_timeout",
            args={},
            cache_policy=CachePolicy(enabled=False),
            breaker_policy=BreakerPolicy(
                failure_threshold=5,
                window_seconds=60,
                cooldown_seconds=30,
            ),
        )

        if result.status == "timeout":
            failure_count += 1
        elif (
            result.status == "error"
            and result.error
            and result.error.get("reason") == "breaker_open"
        ):
            breaker_opened = True
            break

    # Verify breaker opened after threshold
    assert failure_count >= 5, f"Should have at least 5 timeouts, got {failure_count}"
    assert breaker_opened, "Circuit breaker should open after threshold failures"

    # Verify metric
    assert metrics.breaker_opens.get("test_timeout", 0) > 0


# ============================================================================
# GATE 5: FEATURE MAPPER PURITY & DETERMINISM
# ============================================================================


def test_flight_to_choice_is_deterministic() -> None:
    """flight_to_choice should be deterministic: same input → same output."""
    flight = FlightOption(
        flight_id="test-flight-1",
        origin="SEA",
        dest="LHR",
        departure=datetime(2025, 6, 15, 10, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 15, 19, 30, tzinfo=UTC),
        duration_seconds=34200,
        price_usd_cents=85000,
        overnight=True,
        provenance=Provenance(
            source="tool",
            ref_id="test-flight-1",
            source_url="fixture://flights",
            fetched_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    # Call twice
    choice1 = flight_to_choice(flight)
    choice2 = flight_to_choice(flight)

    # Verify identical results
    assert choice1.kind == choice2.kind
    assert choice1.option_ref == choice2.option_ref
    assert choice1.features == choice2.features
    assert choice1.provenance == choice2.provenance


def test_lodging_to_choice_is_deterministic() -> None:
    """lodging_to_choice should be deterministic."""
    lodging = Lodging(
        lodging_id="test-lodge-1",
        name="Test Hotel",
        geo=Geo(lat=51.5074, lon=-0.1278),
        checkin_window={"start": time(14, 0), "end": time(22, 0)},  # type: ignore[arg-type]
        checkout_window={"start": time(6, 0), "end": time(11, 0)},  # type: ignore[arg-type]
        price_per_night_usd_cents=15000,
        tier="mid",  # type: ignore[arg-type]
        kid_friendly=True,
        provenance=Provenance(
            source="tool",
            ref_id="test-lodge-1",
            source_url="fixture://lodging",
            fetched_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice1 = lodging_to_choice(lodging, num_nights=3)
    choice2 = lodging_to_choice(lodging, num_nights=3)

    assert choice1.features == choice2.features
    assert choice1.features.cost_usd_cents == 15000 * 3


def test_attraction_to_choice_is_deterministic() -> None:
    """attraction_to_choice should be deterministic."""
    attraction = Attraction(
        id="test-museum-1",
        name="Test Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=True,
        opening_hours={},
        location=Geo(lat=51.5194, lon=-0.1270),
        est_price_usd_cents=2000,
        provenance=Provenance(
            source="tool",
            ref_id="test-museum-1",
            source_url="fixture://events",
            fetched_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice1 = attraction_to_choice(attraction)
    choice2 = attraction_to_choice(attraction)

    assert choice1.features == choice2.features
    assert choice1.features.indoor is True
    assert "museum" in (choice1.features.themes or [])


def test_transit_to_choice_is_deterministic() -> None:
    """transit_to_choice should be deterministic."""
    transit = TransitLeg(
        mode=TransitMode.metro,
        from_geo=Geo(lat=51.5074, lon=-0.1278),
        to_geo=Geo(lat=51.5194, lon=-0.1270),
        duration_seconds=600,
        last_departure=time(23, 30),
        provenance=Provenance(
            source="tool",
            ref_id="test-transit-1",
            source_url="fixture://transit",
            fetched_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice1 = transit_to_choice(transit)
    choice2 = transit_to_choice(transit)

    assert choice1.features == choice2.features
    assert choice1.features.travel_seconds == 600


def test_feature_mapper_is_pure_no_side_effects() -> None:
    """Feature mappers should have no side effects."""
    # Create a mock object to track if anything gets mutated
    flight = FlightOption(
        flight_id="pure-test",
        origin="SEA",
        dest="LHR",
        departure=datetime(2025, 6, 15, 10, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 15, 19, 30, tzinfo=UTC),
        duration_seconds=34200,
        price_usd_cents=85000,
        overnight=True,
        provenance=Provenance(
            source="tool",
            ref_id="pure-test",
            source_url="fixture://flights",
            fetched_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    # Save original values
    original_id = flight.flight_id
    original_price = flight.price_usd_cents

    # Call mapper
    choice = flight_to_choice(flight)

    # Verify input not mutated
    assert flight.flight_id == original_id
    assert flight.price_usd_cents == original_price

    # Verify output is independent
    assert choice.option_ref == flight.flight_id
    assert choice.features.cost_usd_cents == flight.price_usd_cents


def test_to_choice_universal_converter() -> None:
    """to_choice should dispatch to correct mapper based on type."""
    flight = FlightOption(
        flight_id="universal-test",
        origin="SEA",
        dest="LHR",
        departure=datetime(2025, 6, 15, 10, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 15, 19, 30, tzinfo=UTC),
        duration_seconds=34200,
        price_usd_cents=85000,
        overnight=True,
        provenance=Provenance(
            source="tool",
            ref_id="universal-test",
            source_url="fixture://flights",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice = to_choice(flight)
    assert choice.kind.value == "flight"
    assert choice.option_ref == "universal-test"


def test_to_choice_raises_on_unsupported_type() -> None:
    """to_choice should raise TypeError for unsupported types."""
    with pytest.raises(TypeError, match="Unsupported tool object type"):
        to_choice("not a tool object")  # type: ignore[arg-type]


# ============================================================================
# GATE 6: SELECTOR CANNOT TOUCH RAW TOOL FIELDS (STRUCTURAL)
# ============================================================================


def test_choice_enforces_features_required() -> None:
    """Choice model requires features field - selector cannot bypass."""
    with pytest.raises(ValueError):
        Choice(
            kind="flight",  # type: ignore[arg-type]
            option_ref="test",
            # features intentionally missing
            provenance=Provenance(
                source="tool",
                ref_id="test",
                source_url="test",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )  # type: ignore[call-arg]


def test_choice_features_has_required_fields() -> None:
    """ChoiceFeatures must have cost_usd_cents at minimum."""
    # Valid: only cost_usd_cents (others optional)
    features = ChoiceFeatures(cost_usd_cents=1000)
    assert features.cost_usd_cents == 1000
    assert features.travel_seconds is None
    assert features.indoor is None
    assert features.themes is None

    # Invalid: missing cost_usd_cents
    with pytest.raises(ValueError):
        ChoiceFeatures()  # type: ignore[call-arg]


# ============================================================================
# ADDITIONAL COVERAGE: EDGE CASES
# ============================================================================


def test_flights_for_unknown_route(executor: ToolExecutor) -> None:
    """Flights for unknown route should return empty list."""
    flights = get_flights(
        executor=executor,
        origin="XXX",
        destination="YYY",
        departure_date=date(2025, 6, 15),
    )
    assert flights == []


def test_lodging_for_unknown_city(executor: ToolExecutor) -> None:
    """Lodging for unknown city should return empty list."""
    lodging = get_lodging(executor=executor, city="unknown_city")
    assert lodging == []


def test_events_for_unknown_city(executor: ToolExecutor) -> None:
    """Events for unknown city should return empty list."""
    events = get_events(executor=executor, city="unknown_city")
    assert events == []


def test_fx_rate_unsupported_currency(executor: ToolExecutor) -> None:
    """FX rate for unsupported currency should raise error."""
    with pytest.raises(RuntimeError, match="Unsupported currency"):
        get_fx_rate(executor=executor, from_currency="XXX", to_currency="USD")


def test_transit_distance_calculation(executor: ToolExecutor) -> None:
    """Transit should calculate reasonable durations based on distance."""
    # Two points in London (~1.5 km apart)
    from_geo = Geo(lat=51.5074, lon=-0.1278)  # Trafalgar Square
    to_geo = Geo(lat=51.5194, lon=-0.1270)  # British Museum

    transit = get_transit_legs(
        executor=executor,
        from_geo=from_geo,
        to_geo=to_geo,
        modes=[TransitMode.walk],
    )

    assert len(transit) == 1
    walk = transit[0]

    # Walking at 5 km/h for ~1.5 km should take ~18 minutes (1080 seconds)
    # Allow reasonable range
    assert (
        600 < walk.duration_seconds < 2400
    ), f"Walk duration {walk.duration_seconds}s seems unreasonable"


def test_attraction_tri_state_indoor_field() -> None:
    """Attraction indoor field supports tri-state: True/False/None."""
    # Indoor museum
    museum = Attraction(
        id="museum",
        name="Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=None,
        opening_hours={},
        location=Geo(lat=0, lon=0),
        est_price_usd_cents=0,
        provenance=Provenance(
            source="tool",
            ref_id="museum",
            source_url="test",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice = attraction_to_choice(museum)
    assert choice.features.indoor is True

    # Outdoor park
    park = Attraction(
        id="park",
        name="Park",
        venue_type="park",
        indoor=False,
        kid_friendly=None,
        opening_hours={},
        location=Geo(lat=0, lon=0),
        est_price_usd_cents=0,
        provenance=Provenance(
            source="tool",
            ref_id="park",
            source_url="test",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice = attraction_to_choice(park)
    assert choice.features.indoor is False

    # Mixed/unknown (e.g., Eiffel Tower)
    tower = Attraction(
        id="tower",
        name="Tower",
        venue_type="other",
        indoor=None,
        kid_friendly=None,
        opening_hours={},
        location=Geo(lat=0, lon=0),
        est_price_usd_cents=0,
        provenance=Provenance(
            source="tool",
            ref_id="tower",
            source_url="test",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,
        ),
    )

    choice = attraction_to_choice(tower)
    assert choice.features.indoor is None
