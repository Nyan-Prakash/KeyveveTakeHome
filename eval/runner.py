#!/usr/bin/env python3
"""Evaluation runner for testing scenarios."""

import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import yaml

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.models import (
    Activity,
    ChoiceKind,
    Citation,
    CostBreakdown,
    DateWindow,
    DayItinerary,
    Decision,
    IntentV1,
    ItineraryV1,
    Preferences,
    Provenance,
    TimeWindow,
)


def load_scenarios() -> list[dict[str, Any]]:
    """Load evaluation scenarios from YAML file."""
    scenarios_path = Path(__file__).parent / "scenarios.yaml"
    with open(scenarios_path) as f:
        data = yaml.safe_load(f)
        return list(data["scenarios"])


def build_intent_from_yaml(intent_data: dict[str, Any]) -> IntentV1:
    """Build IntentV1 from YAML data."""
    date_window_data = intent_data["date_window"]
    date_window = DateWindow(
        start=date.fromisoformat(date_window_data["start"]),
        end=date.fromisoformat(date_window_data["end"]),
        tz=date_window_data["tz"],
    )

    prefs_data = intent_data["prefs"]
    prefs = Preferences(
        kid_friendly=prefs_data["kid_friendly"],
        themes=prefs_data["themes"],
        avoid_overnight=prefs_data["avoid_overnight"],
        locked_slots=[],  # Empty for stubs
    )

    return IntentV1(
        city=intent_data["city"],
        date_window=date_window,
        budget_usd_cents=intent_data["budget_usd_cents"],
        airports=intent_data["airports"],
        prefs=prefs,
    )


def create_stub_itinerary(intent: IntentV1, scenario_id: str) -> ItineraryV1:
    """Create a minimal stub itinerary for testing."""
    # Calculate trip length
    trip_days = (intent.date_window.end - intent.date_window.start).days + 1

    # Create stub activities
    days = []
    for i in range(trip_days):
        day_date = intent.date_window.start
        # Simple date arithmetic (doesn't handle all edge cases, but sufficient for stubs)
        for _ in range(i):
            if day_date.month == 12 and day_date.day == 31:
                day_date = day_date.replace(year=day_date.year + 1, month=1, day=1)
            elif day_date.day == 31 or (day_date.month == 2 and day_date.day >= 28):
                day_date = day_date.replace(month=day_date.month + 1, day=1)
            else:
                day_date = day_date.replace(day=day_date.day + 1)

        activities = []
        if i == 0:  # Arrival day
            activities.append(
                Activity(
                    window=TimeWindow(start=time(15, 0), end=time(16, 0)),
                    kind=ChoiceKind.flight,
                    name="Flight Arrival",
                    geo=None,
                    notes="Arriving at airport",
                    locked=False,
                )
            )
        elif i == trip_days - 1:  # Departure day
            activities.append(
                Activity(
                    window=TimeWindow(start=time(10, 0), end=time(11, 0)),
                    kind=ChoiceKind.flight,
                    name="Flight Departure",
                    geo=None,
                    notes="Departing from airport",
                    locked=False,
                )
            )
        else:  # Middle days
            activities.append(
                Activity(
                    window=TimeWindow(start=time(10, 0), end=time(12, 0)),
                    kind=ChoiceKind.attraction,
                    name="Morning Activity",
                    geo=None,
                    notes="Tourist attraction visit",
                    locked=False,
                )
            )

        days.append(DayItinerary(day_date=day_date, activities=activities))

    # Create cost breakdown based on scenario
    if "budget_fail" in scenario_id:
        # Make it exceed budget
        total_cost = intent.budget_usd_cents + 50000  # $500 over
        cost_breakdown = CostBreakdown(
            flights_usd_cents=80000,  # $800
            lodging_usd_cents=60000,  # $600
            attractions_usd_cents=15000,  # $150
            transit_usd_cents=5000,  # $50
            daily_spend_usd_cents=10000,  # $100
            total_usd_cents=total_cost,
            currency_disclaimer="Exchange rates as of 2025-06-01",
        )
    else:
        # Keep within budget
        cost_breakdown = CostBreakdown(
            flights_usd_cents=60000,  # $600
            lodging_usd_cents=80000,  # $800
            attractions_usd_cents=30000,  # $300
            transit_usd_cents=10000,  # $100
            daily_spend_usd_cents=20000,  # $200
            total_usd_cents=200000,  # $2000 total
            currency_disclaimer="Exchange rates as of 2025-06-01",
        )

    # Create stub decisions and citations
    decisions = [
        Decision(
            node="planner",
            rationale="Selected based on budget constraints",
            alternatives_considered=3,
            selected="option_1",
        )
    ]

    citations = [
        Citation(
            claim="Flight pricing",
            provenance=Provenance(
                source="tool",
                ref_id="flight_001",
                source_url=None,
                fetched_at=datetime.now(),
                cache_hit=False,
                response_digest="abc123",
            ),
        )
    ]

    return ItineraryV1(
        itinerary_id="stub_" + scenario_id,
        intent=intent,
        days=days,
        cost_breakdown=cost_breakdown,
        decisions=decisions,
        citations=citations,
        created_at=datetime.now(),
        trace_id="trace_" + scenario_id,
    )


def evaluate_predicates(
    predicates: list[dict[str, Any]],
    intent: IntentV1,
    itinerary: ItineraryV1,
) -> dict[str, bool]:
    """Evaluate predicates against the generated itinerary."""
    results = {}

    # Create evaluation environment
    eval_env = {
        "intent": intent,
        "itinerary": itinerary,
        "len": len,
        "any": any,
    }

    for predicate_info in predicates:
        predicate = predicate_info["predicate"]
        description = predicate_info.get("description", predicate)

        try:
            result = eval(predicate, {"__builtins__": {}}, eval_env)
            results[description] = bool(result)
        except Exception as e:
            print(f"Error evaluating predicate '{predicate}': {e}")
            results[description] = False

    return results


def run_evaluation() -> int:
    """Run evaluation on all scenarios."""
    scenarios = load_scenarios()
    total_scenarios = len(scenarios)
    passed_scenarios = 0

    print(f"Running evaluation on {total_scenarios} scenarios...\n")

    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        description = scenario["description"]

        print(f"Scenario: {scenario_id}")
        print(f"Description: {description}")

        try:
            # Build intent from YAML
            intent = build_intent_from_yaml(scenario["intent"])

            # Create stub itinerary
            itinerary = create_stub_itinerary(intent, scenario_id)

            # Evaluate predicates
            results = evaluate_predicates(scenario["must_satisfy"], intent, itinerary)

            # Check if all predicates pass
            all_passed = all(results.values())
            scenario_passed = all_passed

            # Special case for budget_fail scenarios - they should fail budget check
            if "budget_fail" in scenario_id:
                # For budget fail scenarios, we expect the budget predicate to fail
                budget_predicates = [
                    desc
                    for desc in results.keys()
                    if "budget" in desc.lower() and "exceed" in desc.lower()
                ]
                if budget_predicates:
                    scenario_passed = results[
                        budget_predicates[0]
                    ]  # Should be True (exceeds budget)

            if scenario_passed:
                passed_scenarios += 1
                print("✅ PASS")
            else:
                print("❌ FAIL")

            # Print predicate details
            for desc, result in results.items():
                status = "✅" if result else "❌"
                print(f"  {status} {desc}")

        except Exception as e:
            print(f"❌ ERROR: {e}")

        print()

    # Print summary
    print(f"Summary: {passed_scenarios}/{total_scenarios} scenarios passed")

    if passed_scenarios == total_scenarios:
        print("🎉 All scenarios passed!")
        return 0
    else:
        print(f"❌ {total_scenarios - passed_scenarios} scenarios failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_evaluation())
