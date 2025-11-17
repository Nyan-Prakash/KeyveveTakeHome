"""LangGraph nodes implementing PR6 planner and selector logic."""

import random
import re
from datetime import UTC, datetime, time, timedelta

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


def _extract_venue_info_from_rag(chunks: list[str]) -> dict[int, dict[str, any]]:
    """Extract venue information from RAG chunks.

    Parses chunks to identify venue types, names, and characteristics.

    Args:
        chunks: List of knowledge chunk texts

    Returns:
        Dict mapping index to venue info dict with keys: name, type, indoor
    """
    venue_info_map = {}

    # Keywords for venue type detection
    venue_keywords = {
        "temple": ["temple", "shrine", "sacred", "worship"],
        "garden": ["garden", "park", "botanical"],
        "museum": ["museum", "gallery", "exhibition"],
        "restaurant": ["restaurant", "cafe", "dining", "food"],
        "market": ["market", "shopping", "bazaar"],
        "theater": ["theater", "theatre", "performance"],
        "castle": ["castle", "palace", "fortress"],
        "beach": ["beach", "shore", "coast"],
        "mountain": ["mountain", "peak", "hiking"],
    }

    # Indoor likelihood for each type
    indoor_by_type = {
        "temple": None,  # Can be indoor or outdoor
        "garden": False,
        "museum": True,
        "restaurant": True,
        "market": None,
        "theater": True,
        "castle": None,
        "beach": False,
        "mountain": False,
    }

    idx = 0
    for chunk in chunks:
        chunk_lower = chunk.lower()

        # Extract venue names (look for capitalized words or phrases)
        # Simple heuristic: find words after "visit", "see", "explore"
        name_pattern = r"(?:visit|see|explore|famous for|known for)\s+(?:the\s+)?([A-Z][a-zA-Z\s]{3,30})"
        name_matches = re.findall(name_pattern, chunk)

        # Detect venue type
        detected_type = "attraction"  # Default
        for vtype, keywords in venue_keywords.items():
            if any(keyword in chunk_lower for keyword in keywords):
                detected_type = vtype
                break

        # Extract venue name if found
        venue_name = name_matches[0].strip() if name_matches else None

        if venue_name or detected_type != "attraction":
            venue_info_map[idx] = {
                "name": venue_name,
                "type": detected_type,
                "indoor": indoor_by_type.get(detected_type),
            }
            idx += 1

    return venue_info_map


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
        state.candidate_plans = list(candidate_plans)
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
    if hasattr(state, "candidate_plans") and state.candidate_plans:
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

        branch_features.append(BranchFeatures(plan=plan, features=features))

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


def rag_node(state: OrchestratorState) -> OrchestratorState:
    """Retrieve relevant knowledge chunks from RAG for the destination.

    This node queries the embedding table for knowledge chunks related to
    the destination city, which will be used to enrich attraction data.
    """
    from backend.app.graph.rag import retrieve_knowledge_for_destination

    state.messages.append("Retrieving local knowledge...")
    state.last_event_ts = datetime.now(UTC)

    # Retrieve knowledge chunks for the destination city
    city = state.intent.city
    org_id = state.org_id

    chunks = retrieve_knowledge_for_destination(org_id=org_id, city=city, limit=20)

    if chunks:
        state.rag_chunks = chunks
        state.messages.append(f"Retrieved {len(chunks)} knowledge chunks for {city}")
        state.tool_call_counts["rag"] = len(chunks)
    else:
        state.messages.append(f"No local knowledge found for {city}")
        state.rag_chunks = []

    state.last_event_ts = datetime.now(UTC)
    return state


def tool_exec_node(state: OrchestratorState) -> OrchestratorState:
    """Execute tools to gather data.

    In PR4, this calls fake tools that return static data.
    Real tool execution will use the PR3 ToolExecutor in later PRs.

    For PR9, we populate state dictionaries and track realistic tool call counts
    to enable UI right-rail metrics display.
    """
    from backend.app.models.tool_results import Attraction, WeatherDay

    state.messages.append("Executing tools...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        return state

    # Simulate weather API calls - one per day
    for day_plan in state.plan.days:
        state.weather_by_date[day_plan.date] = WeatherDay(
            forecast_date=day_plan.date,
            precip_prob=0.1,  # 10% chance of rain (sunny)
            wind_kmh=15.0,
            temp_c_high=22.0,
            temp_c_low=12.0,
            provenance=Provenance(
                source="tool",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
            ),
        )
        state.tool_call_counts["weather"] = state.tool_call_counts.get("weather", 0) + 1

    # Fetch real flight data using adapter
    from backend.app.adapters.flights import get_flights

    flight_options = get_flights(
        origin=state.intent.airports[0] if state.intent.airports else "JFK",
        dest=state.intent.city,
        date_window=(state.intent.date_window.start, state.intent.date_window.end),
        avoid_overnight=state.intent.prefs.avoid_overnight if state.intent.prefs else False,
    )

    # Populate state.flights dictionary with real data
    for flight in flight_options:
        state.flights[flight.flight_id] = flight
    state.tool_call_counts["flights"] = len(flight_options)

    # Fetch real lodging data using adapter
    from backend.app.adapters.lodging import get_lodging
    from backend.app.models.common import Tier

    lodging_options = get_lodging(
        city=state.intent.city,
        checkin=state.intent.date_window.start,
        checkout=state.intent.date_window.end,
        tier_prefs=[Tier.budget, Tier.mid, Tier.luxury],
    )

    # Populate state.lodgings dictionary with real data
    for lodging in lodging_options:
        state.lodgings[lodging.lodging_id] = lodging
    state.tool_call_counts["lodging"] = len(lodging_options)

    # Simulate FX tool call
    state.tool_call_counts["fx"] = 1

    # Populate attractions from plan and track tool calls
    # Use RAG chunks to enrich attraction data if available
    attraction_count = 0
    rag_keywords = _extract_venue_info_from_rag(state.rag_chunks)

    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            for choice in slot.choices:
                if (
                    choice.kind == ChoiceKind.attraction
                    and choice.option_ref not in state.attractions
                ):
                    # Try to extract venue info from RAG chunks
                    venue_info = rag_keywords.get(attraction_count % len(rag_keywords)) if rag_keywords else None

                    # Use RAG data if available, otherwise fall back to stub
                    if venue_info:
                        venue_type = venue_info.get("type", "attraction")
                        indoor = venue_info.get("indoor", None)
                        name = venue_info.get("name") or f"Attraction {choice.option_ref}"
                    else:
                        venue_type = "museum"
                        indoor = choice.features.indoor if choice.features.indoor is not None else True
                        name = f"Attraction {choice.option_ref}"

                    state.attractions[choice.option_ref] = Attraction(
                        id=choice.option_ref,
                        name=name,
                        venue_type=venue_type,
                        indoor=indoor,
                        kid_friendly=False,
                        opening_hours={
                            "0": [],  # Monday
                            "1": [],
                            "2": [],
                            "3": [],
                            "4": [],
                            "5": [],
                            "6": [],
                        },
                        location=Geo(lat=48.8566, lon=2.3522),
                        est_price_usd_cents=choice.features.cost_usd_cents,
                        provenance=choice.provenance,
                    )
                    attraction_count += 1

    state.tool_call_counts["attractions"] = attraction_count

    # Simulate transit tool calls (between activities)
    total_activities = sum(len(day.slots) for day in state.plan.days)
    state.tool_call_counts["transit"] = max(0, total_activities - 1)

    state.messages.append(f"Executed {sum(state.tool_call_counts.values())} tool calls")
    state.last_event_ts = datetime.now(UTC)

    return state


def _find_best_flight(
    available_flights: list, desired_features, time_window
):
    """Find best matching flight based on cost preferences.

    Args:
        available_flights: List of FlightOption objects
        desired_features: ChoiceFeatures with target cost
        time_window: TimeWindow for the slot (not used currently)

    Returns:
        Best matching FlightOption or None
    """
    if not available_flights:
        return None

    # Filter by rough cost match (within 50% of desired to be more flexible)
    target_cost = desired_features.cost_usd_cents if desired_features else 50000
    candidates = [
        f for f in available_flights
        if abs(f.price_usd_cents - target_cost) / max(target_cost, 1) < 0.5
    ]

    # Return cheapest if we have matches, otherwise cheapest overall
    candidates = candidates if candidates else available_flights
    return min(candidates, key=lambda f: f.price_usd_cents)


def _find_best_lodging(available_lodging: list, desired_features):
    """Find best matching lodging based on cost preferences.

    Args:
        available_lodging: List of Lodging objects
        desired_features: ChoiceFeatures with target cost

    Returns:
        Best matching Lodging or None
    """
    if not available_lodging:
        return None

    target_cost = desired_features.cost_usd_cents if desired_features else 15000
    candidates = [
        l for l in available_lodging
        if abs(l.price_per_night_usd_cents - target_cost) / max(target_cost, 1) < 0.5
    ]

    candidates = candidates if candidates else available_lodging
    return min(candidates, key=lambda l: l.price_per_night_usd_cents)


def resolve_node(state: OrchestratorState) -> OrchestratorState:
    """Resolve abstract plan choices to concrete tool results with real pricing.

    Maps the planner's abstract choices (with estimated costs) to actual
    flights/lodging/attractions that were fetched by tool_exec_node.
    This ensures the final itinerary uses real pricing data.
    """
    state.messages.append("Resolving plan to actual options with real pricing...")
    state.last_event_ts = datetime.now(UTC)

    if not state.plan:
        state.messages.append("No plan to resolve")
        return state

    resolved_count = 0

    for day_plan in state.plan.days:
        for slot in day_plan.slots:
            # Get the top choice for this slot
            if not slot.choices:
                continue

            choice = slot.choices[0]

            if choice.kind == ChoiceKind.flight:
                # Find best matching flight from available options
                best_flight = _find_best_flight(
                    available_flights=list(state.flights.values()),
                    desired_features=choice.features,
                    time_window=slot.window,
                )
                if best_flight:
                    # Update choice to reference real flight with real price
                    choice.option_ref = best_flight.flight_id
                    if choice.features:
                        choice.features.cost_usd_cents = best_flight.price_usd_cents
                    choice.provenance = Provenance(
                        source="flights_adapter",
                        fetched_at=datetime.now(UTC),
                        cache_hit=False,
                    )
                    resolved_count += 1

            elif choice.kind == ChoiceKind.lodging:
                # Find best matching lodging based on tier preference
                best_lodging = _find_best_lodging(
                    available_lodging=list(state.lodgings.values()),
                    desired_features=choice.features,
                )
                if best_lodging:
                    # Update choice to reference real lodging with real price
                    choice.option_ref = best_lodging.lodging_id
                    if choice.features:
                        choice.features.cost_usd_cents = best_lodging.price_per_night_usd_cents
                    choice.provenance = Provenance(
                        source="lodging_adapter",
                        fetched_at=datetime.now(UTC),
                        cache_hit=False,
                    )
                    resolved_count += 1

    state.messages.append(f"Resolved {resolved_count} choices to real options with accurate pricing")
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
    """Synthesize final itinerary from plan with full provenance tracking.

    PR9: Implements "no evidence, no claim" by generating citations for all
    claims, tracking decisions, and building a complete ItineraryV1 with
    cost breakdown. Emits synthesis metrics.
    """
    from backend.app.metrics import MetricsClient

    start_time = datetime.now(UTC)
    state.messages.append("Synthesizing itinerary...")
    state.last_event_ts = start_time

    if not state.plan:
        state.messages.append("No plan to synthesize")
        return state

    metrics = MetricsClient()

    # Build itinerary from plan with proper tool result lookups
    days: list[DayItinerary] = []
    citations: list[Citation] = []
    decisions: list[Decision] = []

    # Track costs by category
    flights_cost = 0
    lodging_cost = 0
    attractions_cost = 0
    transit_cost = 0

    # Track lodging stays to properly calculate multi-night costs
    # Maps lodging_id -> number of consecutive nights
    lodging_nights: dict[str, int] = {}
    processed_lodging_ids: set[str] = set()

    for day_plan in state.plan.days:
        activities: list[Activity] = []

        for slot in day_plan.slots:
            choice = slot.choices[0]  # Selected choice is first

            # Look up the actual tool result to get name, geo, provenance
            name = f"{choice.kind.value.title()}"
            geo: Geo | None = None
            notes_parts: list[str] = []

            # Resolve tool results based on kind
            if choice.kind == ChoiceKind.flight and choice.option_ref in state.flights:
                flight = state.flights[choice.option_ref]
                name = f"{flight.origin} → {flight.dest}"
                notes_parts.append(f"Departure: {flight.departure.strftime('%H:%M')}")
                flights_cost += flight.price_usd_cents

                # Create citation for flight details
                citations.append(
                    Citation(
                        claim=f"Flight {flight.origin} to {flight.dest}",
                        provenance=flight.provenance,
                    )
                )

            elif (
                choice.kind == ChoiceKind.lodging
                and choice.option_ref in state.lodgings
            ):
                lodging = state.lodgings[choice.option_ref]
                name = lodging.name
                geo = lodging.geo
                notes_parts.append(f"{lodging.tier.value.title()} tier")
                if lodging.kid_friendly:
                    notes_parts.append("Kid-friendly")

                # Track lodging nights (each day with lodging = 1 night)
                lodging_nights[choice.option_ref] = lodging_nights.get(choice.option_ref, 0) + 1

                # Citation for lodging (only add once per unique lodging)
                if choice.option_ref not in processed_lodging_ids:
                    citations.append(
                        Citation(
                            claim=f"Lodging: {lodging.name}",
                            provenance=lodging.provenance,
                        )
                    )
                    processed_lodging_ids.add(choice.option_ref)

            elif (
                choice.kind == ChoiceKind.attraction
                and choice.option_ref in state.attractions
            ):
                attr = state.attractions[choice.option_ref]
                name = attr.name
                geo = attr.location

                # Only add claims if we have evidence
                if attr.indoor is not None:
                    indoor_str = "Indoor" if attr.indoor else "Outdoor"
                    notes_parts.append(indoor_str)

                if attr.kid_friendly is True:
                    notes_parts.append("Kid-friendly")

                if attr.venue_type:
                    notes_parts.append(attr.venue_type.title())

                if attr.est_price_usd_cents is not None:
                    attractions_cost += attr.est_price_usd_cents

                # Citation for attraction
                citations.append(
                    Citation(
                        claim=f"{attr.name} ({attr.venue_type})",
                        provenance=attr.provenance,
                    )
                )

            elif (
                choice.kind == ChoiceKind.transit
                and choice.option_ref in state.transit_legs
            ):
                leg = state.transit_legs[choice.option_ref]
                name = f"{leg.mode.value.title()} transit"
                notes_parts.append(f"~{leg.duration_seconds // 60} minutes")
                transit_cost += choice.features.cost_usd_cents

                # Citation for transit
                citations.append(
                    Citation(
                        claim=f"Transit via {leg.mode.value}",
                        provenance=leg.provenance,
                    )
                )
            else:
                # Fallback: use features but no detailed tool result
                # "No evidence, no claim" - be generic
                state.messages.append(
                    f"Warning: Using estimated cost for {choice.kind.value} {choice.option_ref} "
                    f"(tool result not found)"
                )
                notes_parts.append(f"Estimated cost: ${choice.features.cost_usd_cents / 100:.2f}")

                # Still count cost by type using estimated values
                if choice.kind == ChoiceKind.flight:
                    flights_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.lodging:
                    lodging_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.attraction:
                    attractions_cost += choice.features.cost_usd_cents
                elif choice.kind == ChoiceKind.transit:
                    transit_cost += choice.features.cost_usd_cents

            # Build notes from collected parts
            notes = "; ".join(notes_parts) if notes_parts else "Details not available"

            activities.append(
                Activity(
                    window=slot.window,
                    kind=choice.kind,
                    name=name,
                    geo=geo,
                    notes=notes,
                    locked=slot.locked,
                )
            )

        days.append(DayItinerary(day_date=day_plan.date, activities=activities))

    # Calculate total lodging cost (price_per_night * number of nights)
    for lodging_id, num_nights in lodging_nights.items():
        if lodging_id in state.lodgings:
            lodging = state.lodgings[lodging_id]
            lodging_cost += lodging.price_per_night_usd_cents * num_nights

    # Add weather citations
    for day_date, weather in state.weather_by_date.items():
        citations.append(
            Citation(
                claim=f"Weather forecast for {day_date}",
                provenance=weather.provenance,
            )
        )

    # Build decisions from selector and repair
    # Always create at least one decision for UI display (PR9)
    if hasattr(state, "candidate_plans") and len(state.candidate_plans) > 1:
        decisions.append(
            Decision(
                node="selector",
                rationale="Selected plan based on cost, travel time, and preference fit",
                alternatives_considered=len(state.candidate_plans),
                selected=str(state.plan.rng_seed) if state.plan else "0",
            )
        )
    else:
        # Fallback: create planner decision if no selector ran
        decisions.append(
            Decision(
                node="planner",
                rationale="Generated initial itinerary based on user preferences and constraints",
                alternatives_considered=1,
                selected="initial_plan",
            )
        )

    if state.repair_cycles_run > 0:
        decisions.append(
            Decision(
                node="repair",
                rationale=f"Applied {state.repair_moves_applied} repair moves in {state.repair_cycles_run} cycles",
                alternatives_considered=state.repair_moves_applied,
                selected="repaired_plan",
            )
        )

    # Calculate total cost with daily spend
    daily_spend_total = state.plan.assumptions.daily_spend_est_cents * len(days)
    total_cost = (
        flights_cost
        + lodging_cost
        + attractions_cost
        + transit_cost
        + daily_spend_total
    )

    # Build FX disclaimer
    fx_date = state.intent.date_window.start
    currency_disclaimer = (
        f"FX as-of {fx_date.isoformat()}; "
        f"prices are estimates; verify before booking."
    )

    state.itinerary = ItineraryV1(
        itinerary_id=state.trace_id,
        intent=state.intent,
        days=days,
        cost_breakdown=CostBreakdown(
            flights_usd_cents=flights_cost,
            lodging_usd_cents=lodging_cost,
            attractions_usd_cents=attractions_cost,
            transit_usd_cents=transit_cost,
            daily_spend_usd_cents=daily_spend_total,
            total_usd_cents=total_cost,
            currency_disclaimer=currency_disclaimer,
        ),
        decisions=decisions,
        citations=citations,
        created_at=start_time,
        trace_id=state.trace_id,
    )

    # Emit metrics
    end_time = datetime.now(UTC)
    latency_ms = int((end_time - start_time).total_seconds() * 1000)
    metrics.observe_synthesis_latency(latency_ms)

    # Count claims as number of activities + weather days + decisions
    total_claims = (
        sum(len(day.activities) for day in days)
        + len(state.weather_by_date)
        + len(decisions)
    )
    metrics.observe_citation_coverage(len(citations), total_claims)

    state.messages.append(
        f"Itinerary synthesized: {len(days)} days, {len(citations)} citations"
    )
    state.last_event_ts = end_time
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
