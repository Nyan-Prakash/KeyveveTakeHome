"""Budget verification - SPEC §6.1.

Pure function that verifies plan stays within budget with 10% slippage allowance.
Only counts selected options (first choice in each slot).
"""

from backend.app.metrics.registry import MetricsClient
from backend.app.models.common import ViolationKind
from backend.app.models.intent import IntentV1
from backend.app.models.plan import PlanV1
from backend.app.models.violations import Violation


def verify_budget(
    intent: IntentV1, plan: PlanV1, metrics: MetricsClient | None = None
) -> list[Violation]:
    """Verify plan budget constraint.

    Args:
        intent: User's intent with budget constraint
        plan: Generated plan to verify
        metrics: Optional metrics client for telemetry

    Returns:
        List of violations (empty if budget OK, one violation if exceeded)

    Algorithm per SPEC §6.1:
        - Sum cost_usd_cents from selected options only (slot.choices[0])
        - Sum by type: flight + lodging + (daily_spend * days) + attractions + transit
        - Allow 10% slippage: total <= budget * 1.10
        - If exceeded, return BUDGET violation with delta details
    """
    violations: list[Violation] = []

    # Count days for daily spend calculation
    num_days = len(plan.days)

    # Categorize costs by type from selected choices
    flight_cost = 0
    lodging_cost = 0
    attraction_cost = 0
    transit_cost = 0

    for day_plan in plan.days:
        for slot in day_plan.slots:
            if not slot.choices:
                continue

            # Only count selected option (first choice)
            selected_choice = slot.choices[0]
            cost = selected_choice.features.cost_usd_cents

            # Categorize by kind
            if selected_choice.kind.value == "flight":
                flight_cost += cost
            elif selected_choice.kind.value == "lodging":
                lodging_cost += cost
            elif selected_choice.kind.value == "attraction":
                attraction_cost += cost
            elif selected_choice.kind.value == "transit":
                transit_cost += cost
            # meal would go here if we had it

    # Add daily spend estimate from assumptions
    daily_spend_cost = plan.assumptions.daily_spend_est_cents * num_days

    # Total cost
    total_cost_usd_cents = (
        flight_cost + lodging_cost + attraction_cost + transit_cost + daily_spend_cost
    )

    # Budget with 10% slippage buffer
    budget_usd_cents = intent.budget_usd_cents
    budget_with_slippage = int(budget_usd_cents * 1.10)

    # Emit budget delta metric (always, per SPEC §6.1)
    if metrics:
        metrics.observe_budget_delta(budget_usd_cents, total_cost_usd_cents)

    # Check if over budget
    if total_cost_usd_cents > budget_with_slippage:
        over_by_usd_cents = total_cost_usd_cents - budget_usd_cents

        # Emit budget violation metric
        if metrics:
            metrics.inc_violation("budget_exceeded")

        violations.append(
            Violation(
                kind=ViolationKind.budget_exceeded,
                node_ref="budget_check",
                details={
                    "budget_usd_cents": budget_usd_cents,
                    "total_cost_usd_cents": total_cost_usd_cents,
                    "over_by_usd_cents": over_by_usd_cents,
                    "flight_cost": flight_cost,
                    "lodging_cost": lodging_cost,
                    "attraction_cost": attraction_cost,
                    "transit_cost": transit_cost,
                    "daily_spend_cost": daily_spend_cost,
                },
                blocking=True,
            )
        )

    return violations
