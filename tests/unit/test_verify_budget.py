"""Unit tests for budget verifier - PR7.

Tests verify budget verification logic per SPEC §6.1:
- Only selected options (first choice) count
- 10% slippage allowance
- Correct cost categorization
- Metrics emission
"""

from datetime import UTC, date, datetime, time

import pytest

from backend.app.models.common import ChoiceKind, Provenance, TimeWindow
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.verify.budget import verify_budget


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
    start: time = time(9, 0),
    end: time = time(12, 0),
) -> Slot:
    """Create a test slot with a single choice."""
    return Slot(
        window=TimeWindow(start=start, end=end),
        choices=[
            Choice(
                kind=kind,
                option_ref=f"test_{kind.value}_{cost_usd_cents}",
                features=ChoiceFeatures(
                    cost_usd_cents=cost_usd_cents,
                    travel_seconds=1800,
                    indoor=None,
                    themes=[],
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


def test_budget_under_limit():
    """Test plan well under budget - no violation."""
    intent = create_test_intent(budget_usd_cents=100_000)  # $1000

    # Create a simple 5-day plan with low costs
    days = []
    for day_offset in range(5):
        days.append(
            DayPlan(
                date=date(2025, 6, 1) + __import__("datetime").timedelta(days=day_offset),
                slots=[
                    create_test_slot(ChoiceKind.attraction, cost_usd_cents=500),  # $5
                ],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,  # $10/day
        ),
        rng_seed=42,
    )

    # Total: 5 slots × $5 + 5 days × $10 = $25 + $50 = $75
    # Budget: $1000
    # Well under budget
    violations = verify_budget(intent, plan)

    assert len(violations) == 0, "Should have no violations when under budget"


def test_budget_within_slippage():
    """Test plan within 10% slippage - no violation."""
    intent = create_test_intent(budget_usd_cents=100_000)  # $1000

    # Create a plan that's at 108% of budget (within 110% slippage)
    # Total should be $1080
    # 5 days × $10 daily = $50
    # Remaining for slots: $1080 - $50 = $1030
    # 5 slots × $206 = $1030
    days = []
    for day_offset in range(5):
        days.append(
            DayPlan(
                date=date(2025, 6, 1) + __import__("datetime").timedelta(days=day_offset),
                slots=[
                    create_test_slot(ChoiceKind.attraction, cost_usd_cents=20_600),
                ],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,  # $10/day
        ),
        rng_seed=42,
    )

    violations = verify_budget(intent, plan)

    assert len(violations) == 0, "Should have no violations within 10% slippage"


def test_budget_exceeded():
    """Test plan over budget with slippage - violation."""
    intent = create_test_intent(budget_usd_cents=100_000)  # $1000

    # Create a plan that's at 120% of budget (exceeds 110% slippage)
    # Total should be $1200
    # 5 days × $10 daily = $50
    # Remaining for slots: $1200 - $50 = $1150
    # 5 slots × $230 = $1150
    days = []
    for day_offset in range(5):
        days.append(
            DayPlan(
                date=date(2025, 6, 1) + __import__("datetime").timedelta(days=day_offset),
                slots=[
                    create_test_slot(ChoiceKind.attraction, cost_usd_cents=23_000),
                ],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,  # $10/day
        ),
        rng_seed=42,
    )

    violations = verify_budget(intent, plan)

    assert len(violations) == 1, "Should have one budget violation"
    violation = violations[0]

    assert violation.kind.value == "budget_exceeded"
    assert violation.blocking is True
    assert violation.node_ref == "budget_check"

    # Check details
    assert violation.details["budget_usd_cents"] == 100_000
    assert violation.details["total_cost_usd_cents"] == 120_000
    assert violation.details["over_by_usd_cents"] == 20_000


def test_budget_only_counts_selected_options():
    """Test that only first choice (selected) counts, not alternatives."""
    intent = create_test_intent(budget_usd_cents=100_000)  # $1000

    # Create slots with multiple choices
    # Only first choice should count
    slot_with_alternatives = Slot(
        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
        choices=[
            Choice(  # Selected - cheap
                kind=ChoiceKind.attraction,
                option_ref="selected_cheap",
                features=ChoiceFeatures(
                    cost_usd_cents=500,  # $5
                    travel_seconds=1800,
                    indoor=None,
                    themes=[],
                ),
                score=0.85,
                provenance=Provenance(
                    source="test",
                    fetched_at=datetime.now(UTC),
                    cache_hit=False,
                ),
            ),
            Choice(  # Alternative - expensive (should NOT count)
                kind=ChoiceKind.attraction,
                option_ref="alternative_expensive",
                features=ChoiceFeatures(
                    cost_usd_cents=50_000,  # $500
                    travel_seconds=1800,
                    indoor=None,
                    themes=[],
                ),
                score=0.70,
                provenance=Provenance(
                    source="test",
                    fetched_at=datetime.now(UTC),
                    cache_hit=False,
                ),
            ),
        ],
        locked=False,
    )

    days = []
    for day_offset in range(5):
        days.append(
            DayPlan(
                date=date(2025, 6, 1) + __import__("datetime").timedelta(days=day_offset),
                slots=[slot_with_alternatives],
            )
        )

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=1000,
        ),
        rng_seed=42,
    )

    # Total should be 5 × $5 + 5 × $10 = $25 + $50 = $75
    # If alternatives counted, would be 5 × $500 = $2500 + $50 = $2550
    violations = verify_budget(intent, plan)

    assert len(violations) == 0, "Should only count selected (first) choice"


def test_budget_categorizes_costs():
    """Test that budget verification correctly categorizes costs by type."""
    intent = create_test_intent(budget_usd_cents=200_000)  # $2000

    days = [
        DayPlan(
            date=date(2025, 6, 1),
            slots=[
                create_test_slot(ChoiceKind.flight, cost_usd_cents=30_000),  # $300
                create_test_slot(ChoiceKind.lodging, cost_usd_cents=15_000, start=time(15, 0), end=time(16, 0)),  # $150
            ],
        ),
        DayPlan(
            date=date(2025, 6, 2),
            slots=[
                create_test_slot(ChoiceKind.attraction, cost_usd_cents=2_000),  # $20
                create_test_slot(ChoiceKind.transit, cost_usd_cents=500, start=time(14, 0), end=time(15, 0)),  # $5
            ],
        ),
        DayPlan(
            date=date(2025, 6, 3),
            slots=[
                create_test_slot(ChoiceKind.attraction, cost_usd_cents=1_000),
            ],
        ),
        DayPlan(
            date=date(2025, 6, 4),
            slots=[
                create_test_slot(ChoiceKind.attraction, cost_usd_cents=1_000),
            ],
        ),
    ]

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=5_000,  # $50/day
        ),
        rng_seed=42,
    )

    # Force a violation to check cost breakdown
    intent_low = create_test_intent(budget_usd_cents=10_000)  # $100
    violations = verify_budget(intent_low, plan)

    assert len(violations) == 1
    details = violations[0].details

    assert details["flight_cost"] == 30_000
    assert details["lodging_cost"] == 15_000
    assert details["attraction_cost"] == 4_000  # All 4 attraction slots
    assert details["transit_cost"] == 500
    assert details["daily_spend_cost"] == 20_000  # 4 days × $50
    assert details["total_cost_usd_cents"] == 69_500
