"""Unit tests for weather verifier - PR7.

Tests per SPEC §6.4 and roadmap merge gates:
- Tri-state logic: indoor=False → blocking, indoor=None → advisory, indoor=True → safe
- Weather thresholds (precip >= 0.60 OR wind >= 30 km/h)
- Metrics emission
"""

from datetime import UTC, date, datetime, time

import pytest

from backend.app.models.common import ChoiceKind, Provenance
from backend.app.models.plan import Assumptions, DayPlan
from backend.app.models.tool_results import WeatherDay
from backend.app.verify.weather import verify_weather
from tests.unit.verify_test_helpers import create_test_plan, create_test_slot


def test_good_weather_no_violations():
    """Test that good weather causes no violations regardless of indoor status."""
    # Good weather
    weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.10,  # Low chance of rain
            wind_kmh=10.0,     # Light wind
            temp_c_high=22.0,
            temp_c_low=15.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "outdoor", time(9, 0), time(11, 0), indoor=False),
                create_test_slot(ChoiceKind.attraction, "unknown", time(11, 30), time(13, 30), indoor=None),
                create_test_slot(ChoiceKind.attraction, "indoor", time(14, 0), time(16, 0), indoor=True),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 0, "Good weather should cause no violations"


def test_rainy_outdoor_blocking():
    """Test that outdoor activity (indoor=False) in rain is BLOCKING."""
    # Rainy weather
    weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.80,  # 80% chance of rain (>= 0.60 threshold)
            wind_kmh=15.0,
            temp_c_high=18.0,
            temp_c_low=12.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "outdoor_park", time(10, 0), time(12, 0), indoor=False),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 1
    violation = violations[0]

    assert violation.kind.value == "weather_unsuitable"
    assert violation.blocking is True
    assert violation.details["indoor"] is False
    assert violation.details["severity"] == "blocking"
    assert violation.details["reason"] == "outdoor_activity_bad_weather"
    assert violation.details["precip_prob"] == 0.80


def test_rainy_unknown_advisory():
    """Test that unknown indoor status (indoor=None) in rain is ADVISORY."""
    # Rainy weather
    weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.70,  # 70% chance of rain
            wind_kmh=10.0,
            temp_c_high=16.0,
            temp_c_low=10.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "unknown_venue", time(10, 0), time(12, 0), indoor=None),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 1
    violation = violations[0]

    assert violation.kind.value == "weather_unsuitable"
    assert violation.blocking is False  # Advisory, not blocking
    assert violation.details["indoor"] is None
    assert violation.details["severity"] == "advisory"
    assert violation.details["reason"] == "uncertain_weather"


def test_rainy_indoor_safe():
    """Test that indoor activity (indoor=True) in rain has no violation."""
    # Rainy weather
    weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.90,  # Heavy rain
            wind_kmh=25.0,     # Strong wind
            temp_c_high=15.0,
            temp_c_low=8.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "museum", time(14, 0), time(16, 0), indoor=True),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 0, "Indoor activities should be safe in bad weather"


def test_windy_triggers_violations():
    """Test that high wind (>= 30 km/h) triggers violations."""
    # Windy weather (no rain but high wind)
    weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.10,  # Low rain
            wind_kmh=35.0,     # High wind (>= 30 threshold)
            temp_c_high=20.0,
            temp_c_low=14.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "outdoor_tour", time(10, 0), time(12, 0), indoor=False),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 1
    violation = violations[0]

    assert violation.blocking is True
    assert violation.details["wind_kmh"] == 35.0


def test_rainy_saturday_scenario():
    """Test roadmap merge gate scenario: rainy Saturday with mixed indoor statuses."""
    # Rainy Saturday
    weather_by_date = {
        date(2025, 6, 7): WeatherDay(  # A Saturday
            forecast_date=date(2025, 6, 7),
            precip_prob=0.80,  # 80% rain
            wind_kmh=20.0,
            temp_c_high=17.0,
            temp_c_low=11.0,
            provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
        )
    }

    days = [
        DayPlan(
            date=date(2025, 6, 7),
            slots=[
                create_test_slot(ChoiceKind.attraction, "outdoor_park", time(9, 0), time(11, 0), indoor=False),    # Should be blocking
                create_test_slot(ChoiceKind.attraction, "unknown_venue", time(11, 30), time(13, 30), indoor=None),    # Should be advisory
                create_test_slot(ChoiceKind.attraction, "museum", time(14, 0), time(16, 0), indoor=True),           # Should be safe
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    # Should have 2 violations: 1 blocking, 1 advisory
    assert len(violations) == 2

    blocking_violations = [v for v in violations if v.blocking]
    advisory_violations = [v for v in violations if not v.blocking]

    assert len(blocking_violations) == 1, "Should have 1 blocking violation (outdoor)"
    assert len(advisory_violations) == 1, "Should have 1 advisory violation (unknown)"

    # Verify blocking violation is for outdoor
    assert blocking_violations[0].details["indoor"] is False

    # Verify advisory violation is for unknown
    assert advisory_violations[0].details["indoor"] is None


def test_no_weather_data():
    """Test that missing weather data doesn't cause violations."""
    # Empty weather data
    weather_by_date = {}

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "outdoor_park", time(9, 0), time(11, 0), indoor=False),
                create_test_slot(ChoiceKind.attraction, "unknown_venue", time(11, 30), time(13, 30), indoor=None),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_weather(plan, weather_by_date)

    assert len(violations) == 0, "Missing weather data should not cause violations"
