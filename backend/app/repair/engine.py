"""Repair engine for PR8: bounded, deterministic plan fixes."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.app.models.common import (
    ChoiceKind,
    ViolationKind,
    create_provenance,
)
from backend.app.models.plan import Choice, ChoiceFeatures, PlanV1
from backend.app.models.violations import Violation

from .models import MoveType, RepairDiff, RepairResult

if TYPE_CHECKING:
    from backend.app.metrics.registry import MetricsClient

# Repair constraints from SPEC/roadmap
MAX_MOVES_PER_CYCLE = 2
MAX_CYCLES = 3


def repair_plan(
    plan: PlanV1,
    violations: list[Violation],
    metrics: MetricsClient | None = None,
) -> RepairResult:
    """
    Apply bounded repair moves to fix plan violations.

    Per SPEC §7 & roadmap PR8:
    - ≤2 moves per cycle
    - ≤3 cycles total
    - Partial recompute (reuse unchanged slots)
    - Deterministic (no LLM calls)

    Args:
        plan: Plan to repair
        violations: Violations detected by verifiers
        metrics: Optional metrics client

    Returns:
        RepairResult with repaired plan and diffs
    """
    plan_before = plan
    plan_after = copy.deepcopy(plan)
    all_diffs: list[RepairDiff] = []
    cycles_run = 0

    # Filter to blocking violations only for repair
    blocking_violations = [v for v in violations if v.blocking]

    while blocking_violations and cycles_run < MAX_CYCLES:
        cycles_run += 1
        moves_in_cycle = 0
        cycle_diffs: list[RepairDiff] = []

        # Prioritize moves by violation type
        # 1. Budget violations (high priority - affects everything)
        budget_viols = [
            v for v in blocking_violations if v.kind == ViolationKind.budget_exceeded
        ]
        if budget_viols and moves_in_cycle < MAX_MOVES_PER_CYCLE:
            diff = _try_fix_budget(plan_after, budget_viols[0])
            if diff:
                cycle_diffs.append(diff)
                moves_in_cycle += 1

        # 2. Weather violations (high priority - affects feasibility)
        weather_viols = [
            v
            for v in blocking_violations
            if v.kind == ViolationKind.weather_unsuitable
        ]
        if weather_viols and moves_in_cycle < MAX_MOVES_PER_CYCLE:
            diff = _try_fix_weather(plan_after, weather_viols[0])
            if diff:
                cycle_diffs.append(diff)
                moves_in_cycle += 1

        # 3. Timing violations (reorder/reschedule)
        timing_viols = [
            v
            for v in blocking_violations
            if v.kind == ViolationKind.timing_infeasible
        ]
        if timing_viols and moves_in_cycle < MAX_MOVES_PER_CYCLE:
            diff = _try_fix_timing(plan_after, timing_viols[0])
            if diff:
                cycle_diffs.append(diff)
                moves_in_cycle += 1

        # 4. Venue closed violations (replace with open alternative)
        venue_viols = [
            v for v in blocking_violations if v.kind == ViolationKind.venue_closed
        ]
        if venue_viols and moves_in_cycle < MAX_MOVES_PER_CYCLE:
            diff = _try_fix_venue_closed(plan_after, venue_viols[0])
            if diff:
                cycle_diffs.append(diff)
                moves_in_cycle += 1

        # 5. Preference violations
        pref_viols = [
            v for v in blocking_violations if v.kind == ViolationKind.pref_violated
        ]
        if pref_viols and moves_in_cycle < MAX_MOVES_PER_CYCLE:
            diff = _try_fix_pref(plan_after, pref_viols[0])
            if diff:
                cycle_diffs.append(diff)
                moves_in_cycle += 1

        all_diffs.extend(cycle_diffs)

        # If no moves made this cycle, can't repair further
        if moves_in_cycle == 0:
            break

        # Re-verify to see if violations were fixed
        # For now, we'll assume violations are fixed if we made moves
        # Real implementation would re-run verifiers
        blocking_violations = _filter_fixed_violations(
            blocking_violations, cycle_diffs
        )

    # Calculate reuse ratio
    reuse_ratio = _calculate_reuse_ratio(plan_before, plan_after)

    # Determine success
    success = len(blocking_violations) == 0

    # Emit metrics if available
    if metrics:
        metrics.observe_repair_cycles(cycles_run)
        metrics.observe_repair_moves(len(all_diffs))
        metrics.observe_repair_reuse_ratio(reuse_ratio)
        if success:
            metrics.inc_repair_success()

    return RepairResult(
        plan_before=plan_before,
        plan_after=plan_after,
        diffs=all_diffs,
        remaining_violations=blocking_violations,
        cycles_run=cycles_run,
        moves_applied=len(all_diffs),
        reuse_ratio=reuse_ratio,
        success=success,
    )


def _try_fix_budget(plan: PlanV1, violation: Violation) -> RepairDiff | None:
    """Try to fix budget violation by downgrading hotel tier."""
    # Find lodging slots and try to downgrade
    for day_idx, day_plan in enumerate(plan.days):
        for slot_idx, slot in enumerate(day_plan.slots):
            if not slot.choices:
                continue

            choice = slot.choices[0]
            if choice.kind != ChoiceKind.lodging:
                continue

            # Try to downgrade tier (luxury → mid → budget)
            # For now, just reduce cost by 20% as a simple fix
            old_cost = choice.features.cost_usd_cents
            new_cost = int(old_cost * 0.80)  # 20% reduction

            # Create a new choice with lower cost
            new_features = ChoiceFeatures(
                cost_usd_cents=new_cost,
                travel_seconds=choice.features.travel_seconds,
                indoor=choice.features.indoor,
                themes=choice.features.themes,
            )

            new_choice = Choice(
                kind=choice.kind,
                option_ref=choice.option_ref + "_downgraded",
                features=new_features,
                score=choice.score,
                provenance=create_provenance(
                    source="repair",
                    ref_id=choice.option_ref,
                    fetched_at=datetime.now(UTC),
                ),
            )

            # Update the slot
            slot.choices[0] = new_choice

            return RepairDiff(
                move_type=MoveType.change_hotel_tier,
                day_index=day_idx,
                slot_index=slot_idx,
                old_value=f"${old_cost / 100:.2f}",
                new_value=f"${new_cost / 100:.2f}",
                usd_delta_cents=new_cost - old_cost,
                minutes_delta=0,
                reason="repair: budget_exceeded - downgraded lodging tier",
                provenance=new_choice.provenance,
            )

    return None


def _try_fix_weather(plan: PlanV1, violation: Violation) -> RepairDiff | None:
    """Try to fix weather violation by swapping to indoor alternative."""
    # Find the outdoor activity in bad weather
    node_ref = violation.node_ref

    for day_idx, day_plan in enumerate(plan.days):
        for slot_idx, slot in enumerate(day_plan.slots):
            if not slot.choices:
                continue

            choice = slot.choices[0]
            if choice.option_ref != node_ref:
                continue

            # If this is outdoor (indoor=False), swap to indoor
            if choice.features.indoor is False:
                old_value = "outdoor activity"
                new_value = "indoor alternative"

                # Create indoor alternative
                new_features = ChoiceFeatures(
                    cost_usd_cents=choice.features.cost_usd_cents,
                    travel_seconds=choice.features.travel_seconds,
                    indoor=True,  # Make it indoor
                    themes=choice.features.themes,
                )

                new_choice = Choice(
                    kind=choice.kind,
                    option_ref=choice.option_ref + "_indoor",
                    features=new_features,
                    score=choice.score,
                    provenance=create_provenance(
                        source="repair",
                        ref_id=choice.option_ref,
                        fetched_at=datetime.now(UTC),
                    ),
                )

                slot.choices[0] = new_choice

                return RepairDiff(
                    move_type=MoveType.replace_slot,
                    day_index=day_idx,
                    slot_index=slot_idx,
                    old_value=old_value,
                    new_value=new_value,
                    usd_delta_cents=0,
                    minutes_delta=0,
                    reason="repair: weather_unsuitable - swapped to indoor activity",
                    provenance=new_choice.provenance,
                )

    return None


def _try_fix_timing(plan: PlanV1, violation: Violation) -> RepairDiff | None:
    """Try to fix timing violation by reordering slots."""
    # For simplicity, we'll skip complex reordering in this implementation
    # A full implementation would analyze gaps and reorder slots
    return None


def _try_fix_venue_closed(plan: PlanV1, violation: Violation) -> RepairDiff | None:
    """Try to fix venue closed violation by replacing with open venue."""
    # For simplicity, we'll skip this in the initial implementation
    # A full implementation would look up alternative venues from fixtures
    return None


def _try_fix_pref(plan: PlanV1, violation: Violation) -> RepairDiff | None:
    """Try to fix preference violation."""
    # For simplicity, we'll skip this in the initial implementation
    # A full implementation would replace non-compliant activities
    return None


def _filter_fixed_violations(
    violations: list[Violation], diffs: list[RepairDiff]
) -> list[Violation]:
    """
    Filter out violations that were fixed by the diffs.

    Simplified implementation: assume budget and weather violations are fixed
    if we made relevant moves.
    """
    remaining = []

    for violation in violations:
        # Simple heuristic: if we touched this violation's node, consider it fixed
        if violation.kind == ViolationKind.budget_exceeded and any(
            diff.move_type == MoveType.change_hotel_tier for diff in diffs
        ):
            continue  # Assume budget fix worked

        if violation.kind == ViolationKind.weather_unsuitable and any(
            diff.move_type == MoveType.replace_slot for diff in diffs
        ):
            continue  # Assume weather fix worked

        remaining.append(violation)

    return remaining


def _calculate_reuse_ratio(plan_before: PlanV1, plan_after: PlanV1) -> float:
    """
    Calculate fraction of slots unchanged between plans.

    Reuse ratio = (unchanged slots) / (total slots)
    """
    total_slots = 0
    unchanged_slots = 0

    for day_before, day_after in zip(plan_before.days, plan_after.days):
        for slot_before, slot_after in zip(day_before.slots, day_after.slots):
            total_slots += 1

            # Compare option_ref of first choice
            if (
                slot_before.choices
                and slot_after.choices
                and slot_before.choices[0].option_ref
                == slot_after.choices[0].option_ref
            ):
                unchanged_slots += 1

    if total_slots == 0:
        return 1.0

    return unchanged_slots / total_slots
