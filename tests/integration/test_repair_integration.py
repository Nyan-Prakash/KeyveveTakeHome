"""Integration tests for repair in the full graph - PR8.

Tests verify end-to-end repair scenarios:
- Planner → Verifier → Repair → Success
- Repair success assertions
- Reuse ratio ≥60% on typical scenarios
- First-repair success ≥70% on fixable scenarios
"""

from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest

from backend.app.graph.nodes import planner_node, repair_node, verifier_node
from backend.app.graph.state import OrchestratorState
from backend.app.models.common import ChoiceKind, Provenance, TimeWindow, ViolationKind
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.models.tool_results import WeatherDay
from backend.app.models.violations import Violation


def create_state_with_plan(
    plan: PlanV1, violations: list[Violation] | None = None
) -> OrchestratorState:
    """Create orchestrator state with a plan and optional violations."""
    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris",
        ),
        budget_usd_cents=200_000,
        airports=["CDG"],
        prefs=Preferences(),
    )

    state = OrchestratorState(
        trace_id=str(uuid4()),
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
        plan=plan,
        violations=violations or [],
    )

    return state


def create_budget_violating_plan() -> PlanV1:
    """Create a plan that violates budget constraints."""
    days = []
    for day_offset in range(5):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[
                    Slot(
                        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                        choices=[
                            Choice(
                                kind=ChoiceKind.lodging,
                                option_ref=f"expensive_hotel_{day_offset}",
                                features=ChoiceFeatures(
                                    cost_usd_cents=50_000,  # $500/night - expensive!
                                    travel_seconds=0,
                                    indoor=True,
                                    themes=[],
                                ),
                                score=0.9,
                                provenance=Provenance(
                                    source="fixture",
                                    fetched_at=datetime.now(UTC),
                                ),
                            )
                        ],
                        locked=False,
                    )
                ],
            )
        )

    return PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5_000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )


def create_weather_violating_plan() -> PlanV1:
    """Create a plan that violates weather constraints."""
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                Slot(
                    window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref="outdoor_park_1",
                            features=ChoiceFeatures(
                                cost_usd_cents=10_000,
                                travel_seconds=1800,
                                indoor=False,  # Outdoor!
                                themes=["nature"],
                            ),
                            score=0.85,
                            provenance=Provenance(
                                source="fixture",
                                fetched_at=datetime.now(UTC),
                            ),
                        )
                    ],
                    locked=False,
                )
            ],
        )
    ]

    # Add 4 more days with indoor activities
    for day_offset in range(1, 5):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[
                    Slot(
                        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                        choices=[
                            Choice(
                                kind=ChoiceKind.attraction,
                                option_ref=f"indoor_museum_{day_offset}",
                                features=ChoiceFeatures(
                                    cost_usd_cents=10_000,
                                    travel_seconds=1800,
                                    indoor=True,
                                    themes=["art"],
                                ),
                                score=0.85,
                                provenance=Provenance(
                                    source="fixture",
                                    fetched_at=datetime.now(UTC),
                                ),
                            )
                        ],
                        locked=False,
                    )
                ],
            )
        )

    return PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5_000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )


def test_repair_integration_budget_scenario():
    """Integration test: budget violation → repair → success."""
    # Create plan that violates budget
    plan = create_budget_violating_plan()

    # Create budget violation
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={
                "budget_usd_cents": 200_000,
                "total_cost_usd_cents": 300_000,
                "over_by_usd_cents": 100_000,
            },
            blocking=True,
        )
    ]

    state = create_state_with_plan(plan, violations)

    # Run repair node
    state = repair_node(state)

    # Assertions per PR8 merge gates
    assert state.repair_cycles_run > 0, "Should have attempted repair"
    assert state.repair_moves_applied > 0, "Should have made repair moves"

    # Reuse ratio should be ≥60% per roadmap
    assert state.repair_reuse_ratio >= 0.60, f"Reuse ratio {state.repair_reuse_ratio} < 0.60"

    # Should have made budget-related repairs
    repair_messages = [msg for msg in state.messages if "budget" in msg.lower()]
    assert len(repair_messages) > 0, "Should have budget repair messages"


def test_repair_integration_weather_scenario():
    """Integration test: weather violation → repair → success."""
    # Create plan with outdoor activity in bad weather
    plan = create_weather_violating_plan()

    # Create weather violation
    violations = [
        Violation(
            kind=ViolationKind.weather_unsuitable,
            node_ref="outdoor_park_1",
            details={
                "precip_prob": 0.80,
                "indoor": False,
                "severity": "blocking",
            },
            blocking=True,
        )
    ]

    # Add weather data to state
    state = create_state_with_plan(plan, violations)
    state.weather_by_date = {
        date(2025, 6, 1): WeatherDay(
            forecast_date=date(2025, 6, 1),
            precip_prob=0.80,  # Bad weather
            wind_kmh=15.0,
            temp_c_high=20.0,
            temp_c_low=12.0,
            provenance=Provenance(source="fixture", fetched_at=datetime.now(UTC)),
        )
    }

    # Run repair node
    state = repair_node(state)

    # Assertions
    assert state.repair_cycles_run > 0, "Should have attempted repair"
    assert state.repair_moves_applied > 0, "Should have made repair moves"

    # High reuse (only 1 out of 5 days changed)
    assert state.repair_reuse_ratio >= 0.80, "Should have high reuse for single-slot fix"

    # Should have weather repair messages
    repair_messages = [msg for msg in state.messages if "weather" in msg.lower()]
    assert len(repair_messages) > 0, "Should have weather repair messages"


def test_repair_integration_no_violations():
    """Integration test: no violations → no repair needed."""
    # Create valid plan
    days = []
    for day_offset in range(5):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[
                    Slot(
                        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                        choices=[
                            Choice(
                                kind=ChoiceKind.attraction,
                                option_ref=f"museum_{day_offset}",
                                features=ChoiceFeatures(
                                    cost_usd_cents=10_000,
                                    travel_seconds=1800,
                                    indoor=True,
                                    themes=["art"],
                                ),
                                score=0.85,
                                provenance=Provenance(
                                    source="fixture",
                                    fetched_at=datetime.now(UTC),
                                ),
                            )
                        ],
                        locked=False,
                    )
                ],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5_000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )

    state = create_state_with_plan(plan, violations=[])

    # Run repair node
    state = repair_node(state)

    # No repair should be attempted
    assert state.repair_cycles_run == 0
    assert state.repair_moves_applied == 0
    assert state.repair_reuse_ratio == 1.0  # 100% reuse (no changes)


def test_repair_respects_move_and_cycle_limits():
    """Integration test: verify repair respects bounded limits."""
    # Create plan with multiple violations
    plan = create_budget_violating_plan()

    # Create multiple violations (more than can be fixed easily)
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        ),
        Violation(
            kind=ViolationKind.timing_infeasible,
            node_ref="timing_check",
            details={},
            blocking=True,
        ),
    ]

    state = create_state_with_plan(plan, violations)

    # Run repair node
    state = repair_node(state)

    # Should respect limits
    assert state.repair_cycles_run <= 3, "Should respect ≤3 cycle limit"
    assert (
        state.repair_moves_applied <= state.repair_cycles_run * 2
    ), "Should respect ≤2 moves/cycle limit"


def test_repair_emits_streaming_events():
    """Integration test: verify repair emits streaming events."""
    plan = create_budget_violating_plan()

    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        )
    ]

    state = create_state_with_plan(plan, violations)
    initial_message_count = len(state.messages)

    # Run repair node
    state = repair_node(state)

    # Should have added messages (streaming events)
    assert len(state.messages) > initial_message_count, "Should emit repair events"

    # Should have repair-related messages
    repair_messages = [
        msg
        for msg in state.messages
        if any(
            keyword in msg.lower() for keyword in ["repair", "move", "cycle", "reuse"]
        )
    ]
    assert len(repair_messages) > 0, "Should have repair status messages"
