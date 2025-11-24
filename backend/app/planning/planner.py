"""Plan generation with bounded fan-out."""

import logging
import random
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from backend.app.models.common import ChoiceKind, Provenance, TimeWindow
from backend.app.models.intent import IntentV1, LockedSlot
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.planning.budget_utils import (
    BASELINE_DAILY_COST_CENTS,
    BudgetProfile,
    build_budget_profile,
    cap_daily_spend,
    scale_cost_multiplier,
    target_activity_cost,
    target_flight_cost,
    target_lodging_cost,
    target_meal_cost,
)
from backend.app.planning.transit_injector import inject_transit_between_activities


logger = logging.getLogger(__name__)


def build_candidate_plans(intent: IntentV1, rag_attractions: list | None = None) -> Sequence[PlanV1]:
    """
    Generate 1-4 candidate plans based on the intent.

    This function creates different plan variants with varying emphasis:
    1. Cost-conscious (budget-friendly choices)
    2. Convenience (shorter travel times, central locations)
    3. Experience-focused (higher-rated activities)
    4. Relaxed (more free time, fewer activities)

    Fan-out is capped at 4 plans maximum.
    Results are deterministic based on the intent.

    Args:
        intent: User intent containing preferences and constraints
        rag_attractions: List of actual attractions from RAG database (if available)

    Returns:
        List of 1-4 candidate PlanV1 objects
    """
    # Use deterministic seed based on intent content for reproducibility
    seed = _generate_seed_from_intent(intent)
    rng = random.Random(seed)

    # Calculate trip duration
    start_date = intent.date_window.start
    end_date = intent.date_window.end
    trip_days = (end_date - start_date).days

    # Use the actual trip duration requested

    # Generate up to 4 different plan variants
    budget_profile = build_budget_profile(intent, baseline_per_day_cents=BASELINE_DAILY_COST_CENTS)

    plans: list[PlanV1] = []

    # Plan 1: Cost-conscious
    plans.append(_build_cost_conscious_plan(intent, trip_days, rng, budget_profile, rag_attractions))

    # Only add more plans if budget allows for alternatives
    if intent.budget_usd_cents > 100_000:  # More than $1000
        # Plan 2: Convenience-focused
        plans.append(_build_convenience_plan(intent, trip_days, rng, budget_profile, rag_attractions))

        if intent.budget_usd_cents > 200_000:  # More than $2000
            # Plan 3: Experience-focused
            plans.append(_build_experience_plan(intent, trip_days, rng, budget_profile, rag_attractions))

            if len(intent.prefs.themes or []) > 1:  # Multiple interests
                # Plan 4: Relaxed/varied
                plans.append(_build_relaxed_plan(intent, trip_days, rng, budget_profile, rag_attractions))

    return plans[:4]  # Ensure fan-out cap


def _generate_seed_from_intent(intent: IntentV1) -> int:
    """Generate deterministic seed from intent content."""
    # Create a simple hash from key intent attributes
    content = f"{intent.city}{intent.date_window.start}{intent.budget_usd_cents}"
    content += f"{sorted(intent.airports)}{intent.prefs.kid_friendly}"
    content += f"{sorted(intent.prefs.themes or [])}"
    return hash(content) % (2**31)


def _calculate_budget_multiplier(
    budget_profile: BudgetProfile,
    base_multiplier: float,
) -> float:
    """Calculate budget-aware cost multiplier with continuous adjustments."""
    return scale_cost_multiplier(base_multiplier, budget_profile)


def _build_cost_conscious_plan(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> PlanV1:
    """Build a cost-conscious plan emphasizing budget-friendly options."""
    base_multiplier = 0.7  # More conservative to stay under budget
    adjusted_multiplier = _calculate_budget_multiplier(budget_profile, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=0.8,  # Slightly fewer activities
        variant_name="cost_conscious",
        budget_profile=budget_profile,
        rag_attractions=rag_attractions,
    )


def _build_convenience_plan(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> PlanV1:
    """Build a convenience-focused plan emphasizing shorter travel times."""
    base_multiplier = 0.97  # Slightly reduced to prevent budget overruns
    adjusted_multiplier = _calculate_budget_multiplier(budget_profile, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=1.0,  # Normal activity count
        variant_name="convenience",
        budget_profile=budget_profile,
        rag_attractions=rag_attractions,
    )


def _build_experience_plan(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> PlanV1:
    """Build an experience-focused plan with premium activities."""
    base_multiplier = 1.25  # Reduced from 1.3 to stay within budget
    adjusted_multiplier = _calculate_budget_multiplier(budget_profile, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=1.1,  # More activities
        variant_name="experience",
        budget_profile=budget_profile,
        rag_attractions=rag_attractions,
    )


def _build_relaxed_plan(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> PlanV1:
    """Build a relaxed plan with more free time."""
    base_multiplier = 0.87  # More conservative to prevent overruns
    adjusted_multiplier = _calculate_budget_multiplier(budget_profile, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=0.6,  # Fewer activities, more free time
        variant_name="relaxed",
        budget_profile=budget_profile,
        rag_attractions=rag_attractions,
    )


def _build_plan_variant(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    cost_multiplier: float,
    activity_density: float,
    variant_name: str,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> PlanV1:
    """Build a plan variant with specific characteristics."""
    start_date = intent.date_window.start
    days: list[DayPlan] = []

    density_adjustment = 1.0 + (budget_profile.normalized_pressure * 0.3)
    effective_activity_density = max(0.4, min(activity_density * density_adjustment, 1.3))

    flight_target_cost = target_flight_cost(budget_profile)
    lodging_target_cost = target_lodging_cost(budget_profile)
    activity_target_cost = target_activity_cost(budget_profile)
    meal_target_cost = target_meal_cost(budget_profile)

    # Handle locked slots from intent
    locked_slots_by_day: dict[int, list[LockedSlot]] = {}
    for locked_slot in intent.prefs.locked_slots or []:
        day_offset = locked_slot.day_offset
        if day_offset not in locked_slots_by_day:
            locked_slots_by_day[day_offset] = []
        locked_slots_by_day[day_offset].append(locked_slot)

    for day_offset in range(trip_days):
        current_date = start_date + timedelta(days=day_offset)

        # Start with any locked slots for this day
        slots = []
        
        # Add flight slots for arrival and departure days
        if day_offset == 0:  # Arrival day - add outbound flight
            outbound_flight_choice = Choice(
                kind=ChoiceKind.flight,
                option_ref="outbound_flight_placeholder",  # Will be resolved later
                features=ChoiceFeatures(
                    cost_usd_cents=int(flight_target_cost * cost_multiplier),
                    travel_seconds=28800,  # 8 hours typical
                    indoor=None,
                    themes=None,
                ),
                score=0.8,
                provenance=Provenance(source="planner", fetched_at=datetime.now(UTC)),
            )
            slots.append(Slot(
                window=TimeWindow(start=time(10, 0), end=time(18, 0)),
                choices=[outbound_flight_choice],
                locked=False,
            ))
        
        if day_offset == trip_days - 1:  # Departure day - add return flight
            return_flight_choice = Choice(
                kind=ChoiceKind.flight,
                option_ref="return_flight_placeholder",  # Will be resolved later
                features=ChoiceFeatures(
                    cost_usd_cents=int(flight_target_cost * cost_multiplier),
                    travel_seconds=28800,  # 8 hours typical
                    indoor=None,
                    themes=None,
                ),
                score=0.8,
                provenance=Provenance(source="planner", fetched_at=datetime.now(UTC)),
            )
            slots.append(Slot(
                window=TimeWindow(start=time(14, 0), end=time(22, 0)),
                choices=[return_flight_choice],
                locked=False,
            ))
        if day_offset in locked_slots_by_day:
            for locked_slot in locked_slots_by_day[day_offset]:
                # Convert locked slot to our format
                choice = Choice(
                    kind=ChoiceKind.attraction,  # Default kind for locked slots
                    option_ref=locked_slot.activity_id,
                    features=ChoiceFeatures(
                        cost_usd_cents=int(2000 * cost_multiplier),  # Estimated cost
                        travel_seconds=1800,  # 30 min default travel
                        indoor=None,  # Unknown for locked slots
                        themes=intent.prefs.themes,
                    ),
                    provenance=Provenance(source="user", fetched_at=datetime.now(UTC)),
                )
                slots.append(Slot(
                    window=locked_slot.window,
                    choices=[choice],
                    locked=True,
                ))

        # Fill remaining time with generated activities
        base_activities = int(effective_activity_density * 2)  # 0-3 activities per day
        activities_to_add = max(0, base_activities - len(slots))

        # Generate morning activities
        if activities_to_add > 0 and not _has_slot_in_timerange(slots, time(8, 0), time(12, 0)):
            morning_choice = _create_activity_choice(
                day_offset,
                "morning",
                rng,
                cost_multiplier,
                variant_name,
                intent,
                budget_profile,
                rag_attractions,
            )
            slots.append(Slot(
                window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                choices=[morning_choice],
                locked=False,
            ))
            activities_to_add -= 1

        # Generate afternoon activities
        if activities_to_add > 0 and not _has_slot_in_timerange(slots, time(13, 0), time(18, 0)):
            afternoon_choice = _create_activity_choice(
                day_offset,
                "afternoon",
                rng,
                cost_multiplier,
                variant_name,
                intent,
                budget_profile,
                rag_attractions,
            )
            slots.append(Slot(
                window=TimeWindow(start=time(14, 0), end=time(17, 0)),
                choices=[afternoon_choice],
                locked=False,
            ))
            activities_to_add -= 1

        # Generate evening activities for higher activity density
        if (activities_to_add > 0 and effective_activity_density > 0.8 and
            not _has_slot_in_timerange(slots, time(18, 0), time(22, 0))):
            evening_choice = _create_activity_choice(
                day_offset,
                "evening",
                rng,
                cost_multiplier,
                variant_name,
                intent,
                budget_profile,
                rag_attractions,
            )
            slots.append(Slot(
                window=TimeWindow(start=time(19, 0), end=time(21, 0)),
                choices=[evening_choice],
                locked=False,
            ))

        # Sort slots by start time to avoid overlaps
        slots.sort(key=lambda s: s.window.start)

        days.append(DayPlan(date=current_date, slots=slots))

    # Add lodging choice for entire trip (appears on each day for UI display)
    base_lodging_cost = lodging_target_cost
    lodging_cost = int(max(5_000, min(base_lodging_cost * cost_multiplier, 45_000)))
    lodging_tier = _lodging_tier_from_cost(lodging_cost)

    logger.info(
        f"Lodging selection: budget=${intent.budget_usd_cents/100:.0f}, days={trip_days}, "
        f"per_day=${budget_profile.budget_per_day_cents/100:.0f}, tier={lodging_tier}, "
        f"cost_multiplier={cost_multiplier:.2f}, target_cost=${base_lodging_cost/100:.0f}, "
        f"final_cost=${lodging_cost/100:.0f}/night, "
        f"pressure={budget_profile.normalized_pressure:.2f}"
    )

    # Create lodging choice with unique reference per variant (same across all days)
    lodging_choice = Choice(
        kind=ChoiceKind.lodging,
        option_ref=f"{variant_name}_lodging_{lodging_tier}",
        features=ChoiceFeatures(
            cost_usd_cents=lodging_cost,  # Per night cost
            travel_seconds=0,
            indoor=True,
            themes=["accommodation"],
        ),
        provenance=Provenance(source="planner", fetched_at=datetime.now(UTC)),
    )

    # Add lodging slot to each day for UI display (but cost calculated only once in synthesizer)
    for day_plan in days:
        # Use late evening slot that won't conflict with activities
        lodging_slot = Slot(
            window=TimeWindow(start=time(22, 0), end=time(23, 59)),  # Check-in after evening activities
            choices=[lodging_choice],
            locked=False,
        )
        day_plan.slots.append(lodging_slot)
        
        # Re-sort day slots to maintain chronological order
        day_plan.slots.sort(key=lambda s: s.window.start)

    # Create assumptions based on variant
    fx_rate = 0.92 if variant_name != "experience" else 0.90  # Slightly different rates
    base_daily_spend = int(min(budget_profile.budget_per_day_cents * 0.35, 18_000) * cost_multiplier)
    daily_spend = cap_daily_spend(base_daily_spend, budget_profile)

    plan = PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=fx_rate,
            daily_spend_est_cents=daily_spend,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=rng.randint(0, 2**31 - 1),
    )

    return _enforce_budget(plan, intent)


def _has_slot_in_timerange(slots: list[Slot], start_time: time, end_time: time) -> bool:
    """Check if any existing slot overlaps with the given time range."""
    for slot in slots:
        # Check for any overlap
        if (slot.window.start < end_time and slot.window.end > start_time):
            return True
    return False


def _create_activity_choice(
    day_offset: int,
    period: str,
    rng: random.Random,
    cost_multiplier: float,
    variant_name: str,
    intent: IntentV1,
    budget_profile: BudgetProfile,
    rag_attractions: list | None = None,
) -> Choice:
    """Create an activity choice for a specific time period.

    If RAG attractions are available, selects from real attractions.
    Otherwise, creates abstract slot with estimated costs.
    """

    # Determine activity type based on period and variant
    if period == "morning":
        kind = ChoiceKind.attraction
        base_cost = target_activity_cost(budget_profile)
        themes = ["culture", "art"]
    elif period == "afternoon":
        kind = ChoiceKind.attraction
        base_cost = int(target_activity_cost(budget_profile) * 1.1)
        themes = ["museums", "outdoor"]
    else:  # evening
        kind = ChoiceKind.meal
        base_cost = target_meal_cost(budget_profile)
        themes = ["food", "dining"]

    # Apply user preferences to themes
    if intent.prefs.themes:
        themes = intent.prefs.themes[:2]  # Use first 2 user themes

    # For extremely constrained budgets randomly mix in free options
    if budget_profile.normalized_pressure < -0.4 and kind == ChoiceKind.attraction:
        base_cost = rng.choice([0, base_cost // 2])

    # Apply cost multiplier and add randomness with light clamp
    noisy_multiplier = cost_multiplier * rng.uniform(0.85, 1.15)
    final_cost = int(max(0, min(base_cost * noisy_multiplier, 25_000)))

    # Determine indoor/outdoor based on variant and randomness
    if variant_name == "experience":
        indoor = rng.choice([True, False, None])  # More varied
    elif variant_name == "relaxed":
        indoor = False if period != "evening" else True  # Outdoor during day
    else:
        indoor = rng.choice([True, None])  # Mostly indoor/unknown

    # If RAG attractions available and this is an attraction, try to use real data
    if rag_attractions and kind == ChoiceKind.attraction:
        # Filter attractions by budget compatibility (within ±50% of target cost)
        budget_compatible = [
            attr for attr in rag_attractions
            if attr.est_price_usd_cents is not None and
            abs(attr.est_price_usd_cents - final_cost) / max(final_cost, 1) < 0.5
        ] or rag_attractions  # Fallback to all if none match budget

        # Filter by indoor/outdoor preference if specified
        if indoor is not None:
            preference_match = [
                attr for attr in budget_compatible
                if attr.indoor == indoor
            ]
            if preference_match:
                budget_compatible = preference_match

        # Select a random attraction from compatible options
        if budget_compatible:
            selected_attraction = rng.choice(budget_compatible)
            return Choice(
                kind=kind,
                option_ref=selected_attraction.id,  # Use RAG attraction ID
                features=ChoiceFeatures(
                    cost_usd_cents=selected_attraction.est_price_usd_cents or final_cost,
                    travel_seconds=rng.randint(900, 2400),  # 15-40 minutes travel
                    indoor=selected_attraction.indoor,
                    themes=themes,  # Keep user themes for scoring
                ),
                score=rng.uniform(0.6, 0.9),
                provenance=Provenance(
                    source="planner+rag",
                    ref_id=f"planner:rag:{selected_attraction.id}",
                    fetched_at=datetime.now(UTC),
                ),
            )

    # Fallback: Create abstract slot with estimated costs (when RAG not available or for meals)
    return Choice(
        kind=kind,
        option_ref=f"{variant_name}_{day_offset}_{period}",
        features=ChoiceFeatures(
            cost_usd_cents=final_cost,
            travel_seconds=rng.randint(900, 2400),  # 15-40 minutes travel
            indoor=indoor,
            themes=themes,
        ),
        score=rng.uniform(0.6, 0.9),
        provenance=Provenance(
            source="planner",
            fetched_at=datetime.now(UTC),
        ),
    )


def _lodging_tier_from_cost(cost_cents: int) -> str:
    """Map lodging cost to a display tier name."""
    if cost_cents <= 10_000:
        return "budget"
    if cost_cents <= 24_000:
        return "mid"
    return "luxury"


def _enforce_budget(plan: PlanV1, intent: IntentV1) -> PlanV1:
    """
    Scale plan costs to stay safely within budget.

    Targets 90-95% of budget to leave room for transit, meals, and price variations.
    Must never exceed budget as there is no slippage allowance in verification.
    """
    target_budget = max(intent.budget_usd_cents, 0)
    # Target 95% of budget to leave 5% safety margin for transit/meals added later
    target_utilization = int(target_budget * 0.95)

    for iteration in range(3):
        total_cost = _estimate_plan_cost(plan)

        # Check if we're in the acceptable range (90-95% of budget)
        if 0.90 * target_budget <= total_cost <= 0.95 * target_budget:
            return plan

        # Scale to hit target utilization
        scale_factor = target_utilization / max(total_cost, 1)
        # Conservative scaling: only allow small increases (5%) and larger decreases
        scale_factor = max(0.7, min(scale_factor, 1.25))

        logger.info(
            "Scaling plan costs to better utilize budget",
            extra={
                "iteration": iteration,
                "total_cost_before_cents": total_cost,
                "target_budget_cents": target_budget,
                "target_utilization_cents": target_utilization,
                "scale_factor": scale_factor,
                "utilization_pct": (total_cost / target_budget * 100) if target_budget > 0 else 0,
            },
        )

        _scale_plan_costs(plan, scale_factor)

    return plan


def _estimate_plan_cost(plan: PlanV1) -> int:
    """Estimate plan cost using the same categorization as the verifier."""
    flight_cost = 0
    lodging_cost = 0
    attraction_cost = 0
    transit_cost = 0

    for day_plan in plan.days:
        for slot in day_plan.slots:
            if not slot.choices:
                continue

            selected_choice = slot.choices[0]
            cost = selected_choice.features.cost_usd_cents

            if selected_choice.kind is ChoiceKind.flight:
                flight_cost += cost
            elif selected_choice.kind is ChoiceKind.lodging:
                lodging_cost += cost
            elif selected_choice.kind is ChoiceKind.attraction:
                attraction_cost += cost
            elif selected_choice.kind is ChoiceKind.transit:
                transit_cost += cost
            elif selected_choice.kind is ChoiceKind.meal:
                attraction_cost += cost

    daily_spend_cost = plan.assumptions.daily_spend_est_cents * len(plan.days)

    return flight_cost + lodging_cost + attraction_cost + transit_cost + daily_spend_cost


def _scale_plan_costs(plan: PlanV1, scale_factor: float) -> None:
    """Scale all choice costs (unique choices only) along with daily spend."""
    seen_choices: set[int] = set()

    for day_plan in plan.days:
        for slot in day_plan.slots:
            for choice in slot.choices:
                choice_id = id(choice)
                if choice_id in seen_choices:
                    continue
                seen_choices.add(choice_id)

                original_cost = choice.features.cost_usd_cents
                new_cost = max(0, int(round(original_cost * scale_factor)))
                choice.features.cost_usd_cents = new_cost

    plan.assumptions.daily_spend_est_cents = max(
        0,
        int(round(plan.assumptions.daily_spend_est_cents * scale_factor)),
    )
