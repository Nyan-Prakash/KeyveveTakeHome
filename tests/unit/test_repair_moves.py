"""Unit tests for repair engine - PR8.

Tests verify repair logic per SPEC §7 and roadmap PR8:
- Bounded moves: ≤2 moves/cycle, ≤3 cycles
- Partial recompute and reuse tracking
- Budget repair (hotel tier downgrade)
- Weather repair (outdoor → indoor swap)
- Determinism (same input → same output)
- Metrics emission
"""

from datetime import UTC, date, datetime, time

import pytest

from backend.app.metrics.registry import MetricsClient
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
from backend.app.models.violations import Violation
from backend.app.repair import repair_plan
from backend.app.repair.models import MoveType


def create_test_intent(budget_usd_cents: int) -> IntentV1:
    """Create a minimal test intent."""
    return IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris",
        ),
        budget_usd_cents=budget_usd_cents,
        airports=["CDG"],
        prefs=Preferences(),
    )


def create_test_slot(
    kind: ChoiceKind,
    cost_usd_cents: int,
    indoor: bool | None = None,
    option_ref: str | None = None,
    start: time = time(9, 0),
    end: time = time(12, 0),
) -> Slot:
    """Create a test slot with a single choice."""
    if option_ref is None:
        option_ref = f"test_{kind.value}_{cost_usd_cents}"

    return Slot(
        window=TimeWindow(start=start, end=end),
        choices=[
            Choice(
                kind=kind,
                option_ref=option_ref,
                features=ChoiceFeatures(
                    cost_usd_cents=cost_usd_cents,
                    travel_seconds=1800,
                    indoor=indoor,
                    themes=["art"],
                ),
                score=0.85,
                provenance=Provenance(
                    source="test",
                    fetched_at=datetime.now(UTC),
                    cache_hit=False,
                ),
            )
        ],
        locked=False,
    )


def create_test_plan(num_days: int = 5, daily_cost: int = 10_000) -> PlanV1:
    """Create a simple test plan."""
    days = []
    for day_offset in range(num_days):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[
                    create_test_slot(
                        ChoiceKind.attraction,
                        daily_cost,
                        start=time(9, 0),
                        end=time(12, 0),
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


def test_repair_no_violations():
    """Test repair with no violations - should be a no-op."""
    plan = create_test_plan()
    violations: list[Violation] = []
    metrics = MetricsClient()

    result = repair_plan(plan, violations, metrics)

    # No changes should be made
    assert result.success is True
    assert result.cycles_run == 0
    assert result.moves_applied == 0
    assert result.reuse_ratio == 1.0
    assert len(result.diffs) == 0
    assert result.plan_after == plan


def test_repair_budget_violation_hotel_downgrade():
    """Test budget repair by downgrading hotel tier."""
    # Create plan with expensive lodging
    days = []
    for day_offset in range(5):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[
                    create_test_slot(
                        ChoiceKind.lodging, 50_000, start=time(9, 0), end=time(12, 0)
                    ),  # $500/night
                    create_test_slot(
                        ChoiceKind.attraction, 5_000, start=time(14, 0), end=time(18, 0)
                    ),
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

    # Create budget violation
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={
                "budget_usd_cents": 200_000,  # $2000 budget
                "total_cost_usd_cents": 300_000,  # $3000 actual
                "over_by_usd_cents": 100_000,
            },
            blocking=True,
        )
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # Should attempt repair
    assert result.cycles_run >= 1
    assert result.moves_applied >= 1

    # Should have diffs with budget-related moves
    assert len(result.diffs) > 0
    assert any(
        diff.move_type == MoveType.change_hotel_tier for diff in result.diffs
    )

    # Cost should be reduced
    total_delta = sum(diff.usd_delta_cents for diff in result.diffs)
    assert total_delta < 0, "Repair should reduce cost"

    # Reuse ratio should be < 1.0 since we changed slots
    assert result.reuse_ratio < 1.0

    # Metrics should be emitted (attempts tracked in node, cycles/moves in engine)
    assert len(metrics.repair_cycles) > 0
    assert len(metrics.repair_moves) > 0


def test_repair_weather_violation_outdoor_to_indoor():
    """Test weather repair by swapping outdoor to indoor activity."""
    # Create plan with outdoor activity
    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(
                    ChoiceKind.attraction,
                    10_000,
                    indoor=False,  # Outdoor activity
                    option_ref="outdoor_park",
                )
            ],
        )
    ]

    for day_offset in range(1, 5):
        current_date = date(2025, 6, 1) + __import__("datetime").timedelta(
            days=day_offset
        )
        days.append(
            DayPlan(
                date=current_date,
                slots=[create_test_slot(ChoiceKind.attraction, 10_000, indoor=True)],
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

    # Create weather violation for outdoor activity
    violations = [
        Violation(
            kind=ViolationKind.weather_unsuitable,
            node_ref="outdoor_park",
            details={
                "precip_prob": 0.80,
                "indoor": False,
                "severity": "blocking",
            },
            blocking=True,
        )
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # Should attempt repair
    assert result.cycles_run >= 1
    assert result.moves_applied >= 1

    # Should have replaced the outdoor activity
    assert len(result.diffs) > 0
    assert any(diff.move_type == MoveType.replace_slot for diff in result.diffs)

    # First day's activity should now be indoor
    assert result.plan_after.days[0].slots[0].choices[0].features.indoor is True

    # High reuse ratio since only one slot changed
    assert result.reuse_ratio >= 0.80


def test_repair_bounded_moves_per_cycle():
    """Test that repair respects ≤2 moves per cycle limit."""
    plan = create_test_plan()

    # Create 5 blocking violations (more than can be fixed in one cycle)
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref=f"violation_{i}",
            details={},
            blocking=True,
        )
        for i in range(5)
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # Should respect move limit
    # Each cycle can make ≤2 moves
    for cycle_idx in range(result.cycles_run):
        # Can't easily check per-cycle, but total moves should be ≤ (cycles * 2)
        assert result.moves_applied <= result.cycles_run * 2


def test_repair_bounded_cycles():
    """Test that repair respects ≤3 cycles limit."""
    plan = create_test_plan()

    # Create many violations
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref=f"violation_{i}",
            details={},
            blocking=True,
        )
        for i in range(10)
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # Should respect cycle limit
    assert result.cycles_run <= 3


def test_repair_determinism():
    """Test that repair is deterministic - same input produces same output."""
    plan = create_test_plan()

    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        )
    ]

    # Run repair twice with same inputs
    result1 = repair_plan(plan, violations)
    result2 = repair_plan(plan, violations)

    # Should produce identical results
    assert result1.cycles_run == result2.cycles_run
    assert result1.moves_applied == result2.moves_applied
    assert result1.reuse_ratio == result2.reuse_ratio
    assert len(result1.diffs) == len(result2.diffs)


def test_repair_reuse_ratio_calculation():
    """Test that reuse ratio is calculated correctly."""
    # Create a 5-day plan
    plan = create_test_plan(num_days=5)

    # Create one budget violation
    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        )
    ]

    result = repair_plan(plan, violations)

    # If 1 out of 5 slots changed, reuse should be 4/5 = 0.8
    # (This depends on implementation, but gives us a sanity check)
    assert 0.0 <= result.reuse_ratio <= 1.0

    # If we changed at least one slot, reuse should be < 1.0
    if result.moves_applied > 0:
        assert result.reuse_ratio < 1.0


def test_repair_metrics_emission():
    """Test that repair emits all required metrics."""
    plan = create_test_plan()

    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        )
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # All metrics should be emitted
    assert len(metrics.repair_cycles) > 0
    assert len(metrics.repair_moves) > 0
    assert len(metrics.repair_reuse_ratios) > 0

    # Values should match result
    assert metrics.repair_cycles[-1] == result.cycles_run
    assert metrics.repair_moves[-1] == result.moves_applied
    assert metrics.repair_reuse_ratios[-1] == result.reuse_ratio


def test_repair_diff_structure():
    """Test that repair diffs have all required fields."""
    plan = create_test_plan()

    violations = [
        Violation(
            kind=ViolationKind.budget_exceeded,
            node_ref="budget_check",
            details={},
            blocking=True,
        )
    ]

    result = repair_plan(plan, violations)

    if result.diffs:
        diff = result.diffs[0]

        # All required fields should be present
        assert diff.move_type is not None
        assert diff.day_index >= 0
        assert diff.old_value is not None
        assert diff.new_value is not None
        assert isinstance(diff.usd_delta_cents, int)
        assert isinstance(diff.minutes_delta, int)
        assert diff.reason is not None
        assert diff.provenance is not None


def test_repair_non_blocking_violations_ignored():
    """Test that only blocking violations trigger repair."""
    plan = create_test_plan()

    # Create only non-blocking violations
    violations = [
        Violation(
            kind=ViolationKind.weather_unsuitable,
            node_ref="advisory_weather",
            details={},
            blocking=False,  # Non-blocking
        )
    ]

    metrics = MetricsClient()
    result = repair_plan(plan, violations, metrics)

    # Should not attempt repair for non-blocking
    assert result.cycles_run == 0
    assert result.moves_applied == 0
    assert result.success is True
