"""Unit tests for feasibility verifier - PR7.

Tests per SPEC §6.2–6.3 and roadmap merge gates:
- Split-hours venue test (10-12, 14-18: 13:00 fails, 15:00 passes)
- Timing gaps vs buffers
- DST transitions
- Last train cutoff
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.app.models.common import ChoiceKind, Geo, Provenance
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import Assumptions, DayPlan
from backend.app.models.tool_results import Attraction, Window
from backend.app.verify.feasibility import verify_feasibility
from tests.unit.verify_test_helpers import create_test_intent, create_test_plan, create_test_slot


def test_timing_gap_sufficient():
    """Test that sufficient gaps between slots don't violate."""
    intent = create_test_intent()

    # Two slots with 30-minute gap (exceeds 15-min transit buffer)
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "morning", time(9, 0), time(12, 0)),
                create_test_slot(ChoiceKind.attraction, "afternoon", time(12, 30), time(15, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
            transit_buffer_minutes=15,
        ),
    )

    violations = verify_feasibility(intent, plan, {})

    timing_violations = [v for v in violations if v.kind.value == "timing_infeasible"]
    assert len(timing_violations) == 0, "Should have no timing violations with sufficient gap"


def test_timing_gap_insufficient():
    """Test that insufficient gaps trigger timing violations."""
    intent = create_test_intent()

    # Two slots with 10-minute gap (less than 15-min buffer)
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "morning", time(9, 0), time(12, 0)),
                create_test_slot(ChoiceKind.attraction, "afternoon", time(12, 10), time(15, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
            transit_buffer_minutes=15,
        ),
    )

    violations = verify_feasibility(intent, plan, {})

    timing_violations = [v for v in violations if v.kind.value == "timing_infeasible"]
    assert len(timing_violations) == 1
    violation = timing_violations[0]

    assert violation.blocking is True
    assert violation.details["gap_minutes"] == 10.0
    assert violation.details["required_minutes"] == 15
    assert violation.details["buffer_type"] == "in-city transit"


def test_airport_buffer():
    """Test that flight connections require airport buffer (120 min)."""
    intent = create_test_intent()

    # Flight then hotel with 90-minute gap (less than 120-min airport buffer)
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.flight, "arrival_flight", time(10, 0), time(11, 0)),
                create_test_slot(ChoiceKind.lodging, "hotel", time(12, 30), time(13, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
    )

    violations = verify_feasibility(intent, plan, {})

    timing_violations = [v for v in violations if v.kind.value == "timing_infeasible"]
    assert len(timing_violations) == 1
    violation = timing_violations[0]

    assert violation.details["required_minutes"] == 120
    assert violation.details["buffer_type"] == "airport"


def test_split_hours_venue_closed():
    """Test SPEC §6.3 split-hours case: 10-12, 14-18.

    Slot at 13:00 should violate.
    Slot at 15:00 should pass.
    """
    intent = create_test_intent()
    tz = ZoneInfo("Europe/Paris")

    # Create attraction with split hours
    # June 2, 2025 is Monday (day 0)
    test_date = date(2025, 6, 2)  # Monday
    attraction = Attraction(
        id="louvre",
        name="Louvre Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=True,
        opening_hours={
            "0": [  # Monday
                Window(
                    start=datetime(2025, 6, 2, 10, 0, tzinfo=tz),
                    end=datetime(2025, 6, 2, 12, 0, tzinfo=tz),
                ),
                Window(
                    start=datetime(2025, 6, 2, 14, 0, tzinfo=tz),
                    end=datetime(2025, 6, 2, 18, 0, tzinfo=tz),
                ),
            ]
        },
        location=Geo(lat=48.8606, lon=2.3376),
        est_price_usd_cents=1500,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    # Test 1: Slot at 13:00 (during lunch break) - should fail
    days_fail = [
        DayPlan(
            date=test_date,  # Monday
            slots=[
                create_test_slot(ChoiceKind.attraction, "louvre", time(13, 0), time(13, 30)),
            ],
        )
    ]

    plan_fail = create_test_plan(
        days=days_fail,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations_fail = verify_feasibility(intent, plan_fail, {"louvre": attraction})
    venue_violations_fail = [v for v in violations_fail if v.kind.value == "venue_closed"]

    assert len(venue_violations_fail) == 1, "13:00 slot should violate (lunch break)"
    assert venue_violations_fail[0].details["reason"] == "outside_opening_hours"

    # Test 2: Slot at 15:00 (afternoon window) - should pass
    days_pass = [
        DayPlan(
            date=test_date,  # Monday
            slots=[
                create_test_slot(ChoiceKind.attraction, "louvre", time(15, 0), time(17, 0)),
            ],
        )
    ]

    plan_pass = create_test_plan(
        days=days_pass,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations_pass = verify_feasibility(intent, plan_pass, {"louvre": attraction})
    venue_violations_pass = [v for v in violations_pass if v.kind.value == "venue_closed"]

    assert len(venue_violations_pass) == 0, "15:00 slot should pass (afternoon window)"


def test_venue_closed_no_hours():
    """Test venue with no opening hours for day."""
    intent = create_test_intent()
    tz = ZoneInfo("Europe/Paris")

    # Attraction open only Tuesday-Friday
    attraction = Attraction(
        id="closed_monday",
        name="Closed on Mondays Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=True,
        opening_hours={
            # Monday (0) missing
            "1": [Window(start=datetime(2025, 6, 2, 9, 0, tzinfo=tz), end=datetime(2025, 6, 2, 18, 0, tzinfo=tz))],
        },
        location=Geo(lat=48.8606, lon=2.3376),
        est_price_usd_cents=1500,
        provenance=Provenance(source="test", fetched_at=datetime.now(UTC)),
    )

    days = [
        DayPlan(
            date=date(2025, 6, 1),  # Monday
            slots=[
                create_test_slot(ChoiceKind.attraction, "closed_monday", time(10, 0), time(12, 0)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(fx_rate_usd_eur=0.92, daily_spend_est_cents=1000),
    )

    violations = verify_feasibility(intent, plan, {"closed_monday": attraction})
    venue_violations = [v for v in violations if v.kind.value == "venue_closed"]

    assert len(venue_violations) == 1
    assert venue_violations[0].details["reason"] == "no_opening_hours"


def test_dst_spring_forward():
    """Test DST transition doesn't cause false violations.

    In US/Eastern, March 9, 2025 at 2 AM → 3 AM (spring forward).
    """
    intent = IntentV1(
        city="New York",
        date_window=DateWindow(
            start=date(2025, 3, 9),
            end=date(2025, 3, 12),
            tz="US/Eastern",
        ),
        budget_usd_cents=100_000,
        airports=["JFK"],
        prefs=Preferences(),
    )

    # Activities spanning DST transition
    days = [
        DayPlan(
            date=date(2025, 3, 9),
            slots=[
                # Gap during DST jump shouldn't cause false positive
                create_test_slot(ChoiceKind.attraction, "morning", time(1, 0), time(1, 30)),
                create_test_slot(ChoiceKind.attraction, "after_dst", time(3, 30), time(4, 0)),
                # Real gap is 2 hours due to DST, should pass with 15-min buffer
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
            transit_buffer_minutes=15,
        ),
    )

    violations = verify_feasibility(intent, plan, {})

    timing_violations = [v for v in violations if v.kind.value == "timing_infeasible"]
    assert len(timing_violations) == 0, "DST transition should not cause false timing violation"


def test_last_train_cutoff():
    """Test last train cutoff constraint.

    Activity ending after last_train - buffer should violate.
    """
    intent = create_test_intent()

    # Activity ending at 23:20
    # Last train at 23:30
    # Buffer 15 min
    # Latest acceptable end: 23:15
    # 23:20 > 23:15 → violation
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.attraction, "late_night", time(22, 0), time(23, 20)),
            ],
        )
    ]

    plan = create_test_plan(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
            transit_buffer_minutes=15,
        ),
    )

    violations = verify_feasibility(intent, plan, {}, last_train_cutoff=time(23, 30))

    last_train_violations = [
        v for v in violations
        if v.kind.value == "timing_infeasible"
        and v.details.get("reason") == "last_train_missed"
    ]

    assert len(last_train_violations) == 1
    violation = last_train_violations[0]

    assert violation.blocking is True
    assert violation.details["activity_end"] == "23:20:00"
    assert violation.details["last_train"] == "23:30:00"
    assert violation.details["buffer_minutes"] == 15
