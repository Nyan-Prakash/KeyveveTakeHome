"""Unit tests for preferences verifier - PR7.

Tests per SPEC §6.5:
- Must-have preferences (blocking): avoid_overnight, kid_friendly
- Nice-to-have preferences (advisory): theme coverage
"""

from datetime import UTC, date, datetime, time

import pytest

from backend.app.models.common import ChoiceKind, Geo, Provenance
from backend.app.models.intent import Preferences
from backend.app.models.plan import Assumptions, DayPlan
from backend.app.models.tool_results import Attraction, FlightOption, Window
from backend.app.verify.preferences import verify_preferences
from tests.unit.verify_test_helpers import create_test_intent, create_test_plan, create_test_slot


def test_avoid_overnight_respected():
    """Test that non-overnight flights don't violate avoid_overnight preference."""
    intent = create_test_intent(prefs=Preferences(avoid_overnight=True))

    # Non-overnight flight
    flight = FlightOption(
        flight_id="AF123",
        origin="JFK",
        dest="CDG",
        departure=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 1, 16, 0, tzinfo=UTC),  # Same day
        duration_seconds=21600,
        price_usd_cents=50000,
        overnight=False,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.flight, "AF123"),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {"AF123": flight}, {})

    assert len(violations) == 0, "Non-overnight flight should not violate"


def test_avoid_overnight_violated():
    """Test that overnight flights violate avoid_overnight preference (blocking)."""
    intent = create_test_intent(prefs=Preferences(avoid_overnight=True))

    # Overnight flight
    flight = FlightOption(
        flight_id="AF456",
        origin="JFK",
        dest="CDG",
        departure=datetime(2025, 6, 1, 22, 0, tzinfo=UTC),
        arrival=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),  # Next day
        duration_seconds=43200,
        price_usd_cents=45000,
        overnight=True,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.flight, "AF456"),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {"AF456": flight}, {})

    assert len(violations) == 1
    violation = violations[0]

    assert violation.kind.value == "pref_violated"
    assert violation.blocking is True  # Must-have preference
    assert violation.details["preference"] == "avoid_overnight"
    assert violation.details["reason"] == "overnight_flight_selected"


def test_kid_friendly_no_late_activities():
    """Test that kid_friendly prevents late-night activities (blocking)."""
    intent = create_test_intent(prefs=Preferences(kid_friendly=True))

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                # Activity ending at 19:00 (7 PM) - OK
                create_test_slot(ChoiceKind.attraction, "early_dinner", time(18, 0), time(19, 0)),
                # Activity ending at 21:00 (9 PM) - violation (past 20:00 cutoff)
                create_test_slot(ChoiceKind.attraction, "late_show", time(20, 0), time(21, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {}, {})

    late_night_violations = [
        v for v in violations
        if v.details.get("reason") == "late_night_activity"
    ]

    assert len(late_night_violations) == 1
    violation = late_night_violations[0]

    assert violation.blocking is True
    assert violation.details["preference"] == "kid_friendly"
    assert violation.details["slot_end"] == "21:00:00"
    assert violation.details["cutoff"] == "20:00:00"


def test_kid_friendly_venue_not_suitable():
    """Test that non-kid-friendly venues trigger advisory."""
    from zoneinfo import ZoneInfo

    intent = create_test_intent(prefs=Preferences(kid_friendly=True))
    tz = ZoneInfo("Europe/Paris")

    # Explicitly NOT kid-friendly venue
    attraction_not_kid = Attraction(
        id="nightclub",
        name="Paris Nightclub",
        venue_type="other",
        indoor=True,
        kid_friendly=False,  # Explicit NO
        opening_hours={
            "0": [Window(start=datetime(2025, 6, 1, 22, 0, tzinfo=tz), end=datetime(2025, 6, 2, 4, 0, tzinfo=tz))],
        },
        location=Geo(lat=48.8606, lon=2.3376),
        est_price_usd_cents=5000,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "nightclub", time(10, 0), time(12, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {}, {"nightclub": attraction_not_kid})

    not_kid_friendly_violations = [
        v for v in violations
        if v.details.get("reason") == "not_kid_friendly"
    ]

    assert len(not_kid_friendly_violations) == 1
    violation = not_kid_friendly_violations[0]

    assert violation.blocking is False  # Advisory
    assert violation.details["preference"] == "kid_friendly"
    assert violation.details["kid_friendly"] is False


def test_kid_friendly_unknown_venue():
    """Test that unknown kid-friendliness triggers advisory."""
    from zoneinfo import ZoneInfo

    intent = create_test_intent(prefs=Preferences(kid_friendly=True))
    tz = ZoneInfo("Europe/Paris")

    # Unknown kid-friendly status
    attraction_unknown = Attraction(
        id="museum",
        name="Unknown Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=None,  # Unknown
        opening_hours={
            "0": [Window(start=datetime(2025, 6, 1, 9, 0, tzinfo=tz), end=datetime(2025, 6, 1, 18, 0, tzinfo=tz))],
        },
        location=Geo(lat=48.8606, lon=2.3376),
        est_price_usd_cents=1500,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "museum", time(10, 0), time(12, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {}, {"museum": attraction_unknown})

    unknown_violations = [
        v for v in violations
        if v.details.get("reason") == "unknown_kid_friendly"
    ]

    assert len(unknown_violations) == 1
    violation = unknown_violations[0]

    assert violation.blocking is False  # Advisory
    assert violation.details["kid_friendly"] is None


def test_theme_coverage_sufficient():
    """Test that sufficient theme coverage doesn't violate."""
    intent = create_test_intent(prefs=Preferences(themes=["art", "food"]))

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "museum", time(9, 0), time(11, 0), themes=["art"]),
                create_test_slot(ChoiceKind.attraction, "restaurant", time(12, 0), time(14, 0), themes=["food"]),
                create_test_slot(ChoiceKind.attraction, "gallery", time(15, 0), time(17, 0), themes=["art"]),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {}, {})

    theme_violations = [
        v for v in violations
        if v.details.get("reason") == "low_theme_coverage"
    ]

    assert len(theme_violations) == 0, "100% theme match should not violate"


def test_theme_coverage_insufficient():
    """Test that low theme coverage triggers advisory."""
    intent = create_test_intent(prefs=Preferences(themes=["art", "food"]))

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "museum", time(9, 0), time(11, 0), themes=["art"]),      # Matches
                create_test_slot(ChoiceKind.attraction, "park", time(11, 30), time(13, 30), themes=["nature"]),     # No match
                create_test_slot(ChoiceKind.attraction, "temple", time(14, 0), time(16, 0), themes=["history"]),  # No match
                create_test_slot(ChoiceKind.attraction, "plaza", time(16, 30), time(18, 30), themes=["shopping"]),  # No match
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
        # Padding will add 3 filler days
    )

    violations = verify_preferences(intent, plan, {}, {})

    theme_violations = [
        v for v in violations
        if v.details.get("reason") == "low_theme_coverage"
    ]

    assert len(theme_violations) == 1
    violation = theme_violations[0]

    assert violation.blocking is False  # Advisory (nice-to-have)
    assert violation.details["preference"] == "themes"
    assert violation.details["matching_slots"] == 1
    # With padding, we have 7 total slots (4 from day 1 + 3 filler days)
    assert violation.details["total_slots"] == 7


def test_no_preferences_no_violations():
    """Test that no preferences means no preference violations."""
    intent = create_test_intent(prefs=Preferences())  # Empty preferences

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "anything", time(22, 0), time(23, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_preferences(intent, plan, {}, {})

    assert len(violations) == 0, "No preferences should cause no violations"
