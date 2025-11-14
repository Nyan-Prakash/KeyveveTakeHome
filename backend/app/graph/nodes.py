"""LangGraph nodes implementing PR6 planner and selector logic."""

import random
from datetime import UTC, datetime, time, timedelta

from backend.app.adapters.feature_mapper import (
    map_attraction_to_features,
    map_flight_to_features,
    map_lodging_to_features,
)
from backend.app.models.common import ChoiceKind, Geo, Provenance, TimeWindow
from backend.app.models.itinerary import (
    Activity,
    Citation,
    CostBreakdown,
    DayItinerary,
    Decision,
    ItineraryV1,
)
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.planning import build_candidate_plans, score_branches
from backend.app.planning.types import BranchFeatures

from .state import OrchestratorState


def intent_node(state: OrchestratorState) -> OrchestratorState:
    """Process and normalize the user intent.

    In PR4, this is a simple pass-through that logs the intent.
    Real intent processing will be added in later PRs.
    """
    state.messages.append("Processing intent...")
    state.last_event_ts = datetime.now(UTC)
    return state


def planner_node(state: OrchestratorState) -> OrchestratorState:
    """Generate candidate plans based on the intent using PR6 planner.

    Replaces the PR4 stub implementation with real planning logic
    that generates 1-4 candidate plans with bounded fan-out.
    """
    state.messages.append("Planning itinerary...")
    state.last_event_ts = datetime.now(UTC)

    # Generate candidate plans using PR6 logic
    candidate_plans = build_candidate_plans(state.intent)
    
    # For now, take the first plan as our working plan
    # The selector will choose between alternatives in the next step
    if candidate_plans:
        state.plan = candidate_plans[0]
        state.messages.append(f"Generated {len(candidate_plans)} candidate plans")
        state.messages.append(f"Selected plan with {len(state.plan.days)} days")
        
        # Store all candidates in state for selector to use
        state.candidate_plans = candidate_plans
    else:
        state.messages.append("Failed to generate any candidate plans")
        # Fall back to stub plan
        rng = random.Random(state.seed)
        start_date = state.intent.date_window.start
        days: list[DayPlan] = []

        for day_offset in range(5):
            current_date = start_date + timedelta(days=day_offset)

            # Create 2 slots per day: morning and afternoon
            slots = [
                Slot(
                    window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref=f"fallback_attraction_{day_offset}_morning",
                            features=ChoiceFeatures(
                                cost_usd_cents=rng.randint(1000, 5000),
                                travel_seconds=1800,
                                indoor=rng.choice([True, False, None]),
                                themes=["culture", "art"],
                            ),
                            score=0.85,
                            provenance=Provenance(
                                source="fallback",
                                fetched_at=datetime.now(UTC),
                                cache_hit=False,
                            ),
                        )
                    ],
                    locked=False,
                ),
                Slot(
                    window=TimeWindow(start=time(14, 0), end=time(18, 0)),
                    choices=[
                        Choice(
                            kind=ChoiceKind.attraction,
                            option_ref=f"fallback_attraction_{day_offset}_afternoon",
                            features=ChoiceFeatures(
                                cost_usd_cents=rng.randint(1000, 5000),
                                travel_seconds=1800,
                                indoor=rng.choice([True, False, None]),
                                themes=["food", "nature"],
                            ),
                            score=0.80,
                            provenance=Provenance(
                                source="fallback",
                                fetched_at=datetime.now(UTC),
                                cache_hit=False,
                            ),
                        )
                    ],
                    locked=False,
                ),
            ]

            days.append(DayPlan(date=current_date, slots=slots))

        state.plan = PlanV1(
            days=days,
            assumptions=Assumptions(
                fx_rate_usd_eur=0.92,
                daily_spend_est_cents=10000,
                transit_buffer_minutes=15,
                airport_buffer_minutes=120,
            ),
            rng_seed=state.seed,
        )
        state.candidate_plans = [state.plan]

    state.last_event_ts = datetime.now(UTC)
    return state


def selector_node(state: OrchestratorState) -> OrchestratorState:
    """Select the best plan from candidates using PR6 selector logic.

    Uses feature-based scoring with frozen statistics to rank plans
    and logs score vectors for chosen + top 2 discarded plans.
    """
    state.messages.append("Selecting best plan...")
    state.last_event_ts = datetime.now(UTC)
    
    # Extract features from all candidate plans if available
    if hasattr(state, 'candidate_plans') and state.candidate_plans:
        candidates = state.candidate_plans
    elif state.plan:
        candidates = [state.plan]
    else:
        state.messages.append("No plans available for selection")
        return state
    
    # Build BranchFeatures for each candidate plan
    branch_features: list[BranchFeatures] = []
    for plan in candidates:
        features = []
        for day in plan.days:
            for slot in day.slots:
                for choice in slot.choices:
                    features.append(choice.features)
        
        branch_features.append(BranchFeatures(
            plan=plan,
            features=features
        ))
    
    # Score branches using PR6 selector
    scored_plans = score_branches(branch_features)
    
    if scored_plans:
        # Select the highest-scored plan
        best_plan = scored_plans[0]
        state.plan = best_plan.plan
        state.messages.append(f"Selected plan with score {best_plan.score:.3f}")
        state.messages.append(f"Evaluated {len(scored_plans)} alternatives")
    else:
        state.messages.append("No valid scored plans available")
    
    state.last_event_ts = datetime.now(UTC)
    return state


def tool_exec_node(state: OrchestratorState) -> OrchestratorState:
    """Execute tools to gather data.

    In PR4, this calls fake tools that return static data.
    Real tool execution will use the PR3 ToolExecutor in later PRs.
    """
    state.messages.append("Executing tools...")
    state.last_event_ts = datetime.now(UTC)

    # Fake tool execution - just sleep briefly to simulate work
    state.messages.append("Weather tool: sunny forecast for all days")
    state.messages.append("Currency tool: USD to EUR = 0.92")
    state.last_event_ts = datetime.now(UTC)
    return state


def verifier_node(state: OrchestratorState) -> OrchestratorState:
    """Verify plan constraints using PR7 verifiers.

    Runs all four verifiers:
    - Budget (with 10% slippage)
    - Feasibility (timing + venue hours + DST + last train)
    - Weather (tri-state logic)
    - Preferences (must-have vs nice-to-have)

    Emits metrics and updates state.violations.
    """
    from backend.app.metrics import MetricsClient
    from backend.app.verify import (
        verify_budget,
        verify_feasibility,
        verify_preferences,
        verify_weather,
    )

    state.messages.append("Verifying plan constraints...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        state.messages.append("No plan to verify")
        return state

    # Initialize metrics client
    metrics = MetricsClient()

    # Clear previous violations
    state.violations = []

    # Run budget verifier
    budget_violations = verify_budget(state.intent, state.plan)
    state.violations.extend(budget_violations)

    # Emit budget metrics
    total_cost = 0
    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            if slot.choices:
                total_cost += slot.choices[0].features.cost_usd_cents
    total_cost += state.plan.assumptions.daily_spend_est_cents * len(state.plan.days)

    metrics.observe_budget_delta(state.intent.budget_usd_cents, total_cost)

    if budget_violations:
        for violation in budget_violations:
            metrics.inc_violation(violation.kind.value)

    # Run feasibility verifier
    feasibility_violations = verify_feasibility(
        state.intent,
        state.plan,
        state.attractions,
    )
    state.violations.extend(feasibility_violations)

    if feasibility_violations:
        for violation in feasibility_violations:
            metrics.inc_violation(violation.kind.value)
            if violation.kind.value == "timing_infeasible":
                reason = violation.details.get("reason", "timing")
                metrics.inc_feasibility_violation(reason)
            elif violation.kind.value == "venue_closed":
                metrics.inc_feasibility_violation("venue_closed")

    # Run weather verifier
    weather_violations = verify_weather(state.plan, state.weather_by_date)
    state.violations.extend(weather_violations)

    if weather_violations:
        for violation in weather_violations:
            metrics.inc_violation(violation.kind.value)
            if violation.blocking:
                metrics.inc_weather_blocking()
            else:
                metrics.inc_weather_advisory()

    # Run preferences verifier
    pref_violations = verify_preferences(
        state.intent,
        state.plan,
        state.flights,
        state.attractions,
    )
    state.violations.extend(pref_violations)

    if pref_violations:
        for violation in pref_violations:
            metrics.inc_violation(violation.kind.value)
            pref = violation.details.get("preference", "unknown")
            metrics.inc_pref_violation(pref)

    # Log results
    blocking_count = sum(1 for v in state.violations if v.blocking)
    advisory_count = len(state.violations) - blocking_count

    if state.violations:
        state.messages.append(
            f"Found {len(state.violations)} violations "
            f"({blocking_count} blocking, {advisory_count} advisory)"
        )
    else:
        state.messages.append("No violations detected")

    state.last_event_ts = datetime.now(UTC)
    return state


def repair_node(state: OrchestratorState) -> OrchestratorState:
    """Repair plan violations using PR8 repair engine.

    Applies bounded repair moves to fix violations:
    - ≤2 moves per cycle
    - ≤3 cycles total
    - Partial recompute with reuse tracking
    - Streams repair decisions as events
    """
    from backend.app.metrics import MetricsClient
    from backend.app.repair import repair_plan

    state.messages.append("Checking for repairs...")
    state.last_event_ts = datetime.now(UTC)

    # Check if we have blocking violations to repair
    blocking_violations = [v for v in state.violations if v.blocking]

    if not blocking_violations:
        state.messages.append("No blocking violations - no repairs needed")
        state.last_event_ts = datetime.now(UTC)
        return state

    if not state.plan:
        state.messages.append("No plan to repair")
        state.last_event_ts = datetime.now(UTC)
        return state

    # Initialize metrics client
    metrics = MetricsClient()

    # Store plan before repair
    state.plan_before_repair = state.plan

    # Log repair attempt
    state.messages.append(
        f"Attempting to repair {len(blocking_violations)} blocking violations"
    )
    metrics.inc_repair_attempt()

    # Run repair engine
    result = repair_plan(
        plan=state.plan,
        violations=state.violations,
        metrics=metrics,
    )

    # Update state with repair results
    state.plan = result.plan_after
    state.violations = result.remaining_violations
    state.repair_cycles_run = result.cycles_run
    state.repair_moves_applied = result.moves_applied
    state.repair_reuse_ratio = result.reuse_ratio

    # Stream repair decision events
    for diff in result.diffs:
        state.messages.append(
            f"Repair move: {diff.move_type.value} on day {diff.day_index} - {diff.reason}"
        )

    # Log final results
    if result.success:
        state.messages.append(
            f"Repair successful: {result.moves_applied} moves in {result.cycles_run} cycles, "
            f"{result.reuse_ratio:.0%} reuse"
        )
    else:
        state.messages.append(
            f"Repair incomplete: {len(result.remaining_violations)} violations remain after "
            f"{result.cycles_run} cycles"
        )

    state.last_event_ts = datetime.now(UTC)
    return state


def synth_node(state: OrchestratorState) -> OrchestratorState:
    """Synthesize final itinerary from plan.

    In PR4, this builds a trivial itinerary from the plan.
    Real synthesis logic will be added in later PRs.
    """
    state.messages.append("Synthesizing itinerary...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        state.messages.append("No plan to synthesize")
        return state

    # Build itinerary from plan
    days: list[DayItinerary] = []
    total_cost = 0

    for day_plan in state.plan.days:
        activities: list[Activity] = []
        for slot in day_plan.slots:
            choice = slot.choices[0]  # Take first choice
            total_cost += choice.features.cost_usd_cents
            activities.append(
                Activity(
                    window=slot.window,
                    kind=choice.kind,
                    name=f"Fake {choice.kind.value} activity",
                    geo=Geo(lat=48.8566, lon=2.3522),  # Paris coordinates
                    notes=f"Score: {choice.score}",
                    locked=slot.locked,
                )
            )

        days.append(DayItinerary(day_date=day_plan.date, activities=activities))

    state.itinerary = ItineraryV1(
        itinerary_id=state.trace_id,
        intent=state.intent,
        days=days,
        cost_breakdown=CostBreakdown(
            flights_usd_cents=50000,
            lodging_usd_cents=30000,
            attractions_usd_cents=total_cost,
            transit_usd_cents=5000,
            daily_spend_usd_cents=10000 * len(days),
            total_usd_cents=50000 + 30000 + total_cost + 5000 + (10000 * len(days)),
            currency_disclaimer="Exchange rates are approximate and may vary.",
        ),
        decisions=[
            Decision(
                node="planner",
                rationale="Generated simple 5-day itinerary",
                alternatives_considered=1,
                selected="plan_v1",
            )
        ],
        citations=[
            Citation(
                claim="Weather forecast",
                provenance=Provenance(source="fake", fetched_at=datetime.now(UTC)),
            )
        ],
        created_at=datetime.now(UTC),
        trace_id=state.trace_id,
    )

    state.messages.append("Itinerary synthesized successfully")
    state.last_event_ts = datetime.now(UTC)
    return state


def responder_node(state: OrchestratorState) -> OrchestratorState:
    """Finalize and mark run as complete.

    This is the terminal node that marks the run as done.
    """
    state.messages.append("Finalizing itinerary...")
    state.last_event_ts = datetime.now(UTC)

    state.done = True
    state.messages.append("Run completed successfully")
    state.last_event_ts = datetime.now(UTC)

    return state
