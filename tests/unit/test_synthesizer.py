"""PR9: Unit tests for synthesizer node and citation coverage.

Tests "no evidence, no claim" principle and citation tracking.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

from backend.app.graph.nodes import synth_node
from backend.app.graph.state import OrchestratorState
from backend.app.models.common import (
    ChoiceKind,
    Geo,
    Tier,
    TimeWindow,
    create_provenance,
)
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.models.tool_results import Attraction, FlightOption, Lodging


@pytest.fixture
def sample_state() -> OrchestratorState:
    """Create a state with a simple plan for testing."""
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=4)

    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(start=start, end=end, tz="Europe/Paris"),
        budget_usd_cents=300000,
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False, themes=["art"], avoid_overnight=False, locked_slots=[]
        ),
    )

    # Create a simple 4-day plan
    days = [
        DayPlan(
            date=start + timedelta(days=i),
            slots=[
                Slot(
                    window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref=f"attr_{i}",
                            features=ChoiceFeatures(
                                cost_usd_cents=2000, indoor=True, themes=["art"]
                            ),
                            score=0.9,
                            provenance=create_provenance("fixture"),
                        )
                    ],
                    locked=False,
                ),
            ],
        )
        for i in range(4)
    ]

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )

    return OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
        plan=plan,
    )


def test_synthesizer_creates_itinerary(sample_state: OrchestratorState) -> None:
    """Test that synthesizer creates a valid ItineraryV1."""
    result = synth_node(sample_state)

    assert result.itinerary is not None
    assert len(result.itinerary.days) == 4
    assert result.itinerary.cost_breakdown.total_usd_cents > 0
    assert result.itinerary.trace_id == sample_state.trace_id


def test_synthesizer_with_full_tool_results(sample_state: OrchestratorState) -> None:
    """Test synthesizer with complete tool results creates proper citations."""
    # Add tool results to state
    sample_state.attractions["attr_0"] = Attraction(
        id="attr_0",
        name="Louvre Museum",
        venue_type="museum",
        indoor=True,
        kid_friendly=False,
        opening_hours={
            "0": [],  # Monday closed
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
            "6": [],
        },
        location=Geo(lat=48.8606, lon=2.3376),
        est_price_usd_cents=2000,
        provenance=create_provenance("fixture", ref_id="louvre"),
    )

    sample_state.weather_by_date[sample_state.plan.days[0].date] = pytest.importorskip(
        "backend.app.models.tool_results"
    ).WeatherDay(
        forecast_date=sample_state.plan.days[0].date,
        precip_prob=0.2,
        wind_kmh=10.0,
        temp_c_high=20.0,
        temp_c_low=12.0,
        provenance=create_provenance("weather_api"),
    )

    result = synth_node(sample_state)

    # Check itinerary was created
    assert result.itinerary is not None
    assert len(result.itinerary.days) == 4

    # Check citations include attraction and weather
    citations = result.itinerary.citations
    assert len(citations) > 0

    # Check at least one citation for attraction
    attraction_citations = [
        c for c in citations if "Louvre" in c.claim or "museum" in c.claim
    ]
    assert len(attraction_citations) > 0

    # Check citation has provenance
    for citation in citations:
        assert citation.provenance is not None
        assert citation.provenance.source in [
            "fixture",
            "weather_api",
            "tool",
            "rag",
            "user",
        ]


def test_synthesizer_no_evidence_no_claim(sample_state: OrchestratorState) -> None:
    """Test that synthesizer does not fabricate data without tool results.

    When tool results are missing, synthesizer should use generic
    descriptions rather than inventing specific details.
    """
    # Don't add any tool results - synthesizer should handle gracefully
    result = synth_node(sample_state)

    assert result.itinerary is not None

    # Activities should exist but with generic names
    day0 = result.itinerary.days[0]
    activity = day0.activities[0]

    # Should have a name (kind-based fallback)
    assert activity.name is not None
    assert len(activity.name) > 0

    # Notes should indicate data not available or use features
    assert activity.notes is not None
    # Should either say "Details not available" or show cost from features
    assert "Details not available" in activity.notes or "$" in activity.notes


def test_synthesizer_citation_coverage() -> None:
    """Test citation coverage calculation for merge gate.

    Per roadmap: provenance coverage ≥ 0.95 on golden case.
    """
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=4)

    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(start=start, end=end, tz="Europe/Paris"),
        budget_usd_cents=300000,
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False, themes=["art"], avoid_overnight=False, locked_slots=[]
        ),
    )

    # Create plan with 4 days, 1 slot each
    days = []
    for i in range(4):
        days.append(
            DayPlan(
                date=start + timedelta(days=i),
                slots=[
                    Slot(
                        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                        choices=[
                            Choice(
                                kind=ChoiceKind.attraction,
                                option_ref=f"attr_{i}",
                                features=ChoiceFeatures(
                                    cost_usd_cents=2000, indoor=True, themes=["art"]
                                ),
                                score=0.9,
                                provenance=create_provenance("fixture"),
                            )
                        ],
                        locked=False,
                    ),
                ],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )

    state = OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
        plan=plan,
    )

    # Add all tool results for full coverage
    for i in range(4):
        state.attractions[f"attr_{i}"] = Attraction(
            id=f"attr_{i}",
            name=f"Museum {i}",
            venue_type="museum",
            indoor=True,
            kid_friendly=False,
            opening_hours={
                "0": [],
                "1": [],
                "2": [],
                "3": [],
                "4": [],
                "5": [],
                "6": [],
            },
            location=Geo(lat=48.8606, lon=2.3376),
            est_price_usd_cents=2000,
            provenance=create_provenance("fixture", ref_id=f"museum_{i}"),
        )

    # Add weather for each day
    WeatherDay = pytest.importorskip("backend.app.models.tool_results").WeatherDay
    for i in range(4):
        day_date = start + timedelta(days=i)
        state.weather_by_date[day_date] = WeatherDay(
            forecast_date=day_date,
            precip_prob=0.2,
            wind_kmh=10.0,
            temp_c_high=20.0,
            temp_c_low=12.0,
            provenance=create_provenance("weather_api"),
        )

    result = synth_node(state)

    # Calculate coverage
    citations = result.itinerary.citations
    # Expected claims: 4 activities + 4 weather days = 8
    # Each should have a citation
    expected_claims = 8

    coverage = len(citations) / expected_claims if expected_claims > 0 else 0.0

    # Assert coverage ≥ 0.95 (per merge gate)
    assert coverage >= 0.95, f"Citation coverage {coverage:.2%} below 95% threshold"


def test_synthesizer_cost_breakdown_accuracy(sample_state: OrchestratorState) -> None:
    """Test that cost breakdown accurately reflects selected choices."""
    # Add flight and lodging
    sample_state.flights["flight_1"] = FlightOption(
        flight_id="flight_1",
        origin="CDG",
        dest="PAR",
        departure=datetime.now(UTC),
        arrival=datetime.now(UTC) + timedelta(hours=1),
        duration_seconds=3600,
        price_usd_cents=50000,
        overnight=False,
        provenance=create_provenance("fixture"),
    )

    sample_state.lodgings["lodging_1"] = Lodging(
        lodging_id="lodging_1",
        name="Hotel Paris",
        geo=Geo(lat=48.8566, lon=2.3522),
        checkin_window=TimeWindow(start=time(15, 0), end=time(23, 0)),
        checkout_window=TimeWindow(start=time(7, 0), end=time(11, 0)),
        price_per_night_usd_cents=15000,
        tier=Tier.mid,
        kid_friendly=False,
        provenance=create_provenance("fixture"),
    )

    # Update plan to include these
    flight_choice = Choice(
        kind=ChoiceKind.flight,
        option_ref="flight_1",
        features=ChoiceFeatures(cost_usd_cents=50000),
        score=0.9,
        provenance=create_provenance("fixture"),
    )

    lodging_choice = Choice(
        kind=ChoiceKind.lodging,
        option_ref="lodging_1",
        features=ChoiceFeatures(cost_usd_cents=15000),
        score=0.9,
        provenance=create_provenance("fixture"),
    )

    # Add to first day
    sample_state.plan.days[0].slots.insert(
        0,
        Slot(
            window=TimeWindow(start=time(8, 0), end=time(9, 0)),
            choices=[flight_choice],
            locked=False,
        ),
    )
    sample_state.plan.days[0].slots.insert(
        1,
        Slot(
            window=TimeWindow(start=time(15, 0), end=time(16, 0)),
            choices=[lodging_choice],
            locked=False,
        ),
    )

    result = synth_node(sample_state)

    breakdown = result.itinerary.cost_breakdown

    # Check breakdown includes flight and lodging
    assert breakdown.flights_usd_cents >= 50000
    assert breakdown.lodging_usd_cents >= 15000
    assert breakdown.total_usd_cents > 0

    # Total should be sum of parts
    expected_total = (
        breakdown.flights_usd_cents
        + breakdown.lodging_usd_cents
        + breakdown.attractions_usd_cents
        + breakdown.transit_usd_cents
        + breakdown.daily_spend_usd_cents
    )
    assert breakdown.total_usd_cents == expected_total


def test_synthesizer_decisions_tracking(sample_state: OrchestratorState) -> None:
    """Test that decisions are tracked when selector/repair ran."""
    # Simulate selector ran with multiple candidates
    sample_state.candidate_plans = [sample_state.plan, sample_state.plan]

    # Simulate repair ran
    sample_state.repair_cycles_run = 2
    sample_state.repair_moves_applied = 3

    result = synth_node(sample_state)

    decisions = result.itinerary.decisions

    # Should have decisions for selector and repair
    assert len(decisions) >= 2

    # Check selector decision
    selector_decisions = [d for d in decisions if d.node == "selector"]
    assert len(selector_decisions) == 1
    assert selector_decisions[0].alternatives_considered == 2

    # Check repair decision
    repair_decisions = [d for d in decisions if d.node == "repair"]
    assert len(repair_decisions) == 1
    assert (
        "2 cycles" in repair_decisions[0].rationale
        or "3 moves" in repair_decisions[0].rationale
    )
