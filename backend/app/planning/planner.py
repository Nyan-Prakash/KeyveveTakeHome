"""Plan generation with bounded fan-out."""

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
from backend.app.planning.transit_injector import inject_transit_between_activities


def build_candidate_plans(intent: IntentV1) -> Sequence[PlanV1]:
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
    plans: list[PlanV1] = []

    # Plan 1: Cost-conscious
    plans.append(_build_cost_conscious_plan(intent, trip_days, rng))

    # Only add more plans if budget allows for alternatives
    if intent.budget_usd_cents > 100_000:  # More than $1000
        # Plan 2: Convenience-focused
        plans.append(_build_convenience_plan(intent, trip_days, rng))

        if intent.budget_usd_cents > 200_000:  # More than $2000
            # Plan 3: Experience-focused
            plans.append(_build_experience_plan(intent, trip_days, rng))

            if len(intent.prefs.themes or []) > 1:  # Multiple interests
                # Plan 4: Relaxed/varied
                plans.append(_build_relaxed_plan(intent, trip_days, rng))

    return plans[:4]  # Ensure fan-out cap


def _generate_seed_from_intent(intent: IntentV1) -> int:
    """Generate deterministic seed from intent content."""
    # Create a simple hash from key intent attributes
    content = f"{intent.city}{intent.date_window.start}{intent.budget_usd_cents}"
    content += f"{sorted(intent.airports)}{intent.prefs.kid_friendly}"
    content += f"{sorted(intent.prefs.themes or [])}"
    return hash(content) % (2**31)


def _calculate_budget_multiplier(intent: IntentV1, trip_days: int, base_multiplier: float) -> float:
    """Calculate budget-aware cost multiplier.

    Scales the base variant multiplier based on budget pressure, ensuring
    that when budget is reduced, the planner generates genuinely cheaper plans.

    Args:
        intent: User intent with budget information
        trip_days: Number of days in the trip
        base_multiplier: Base cost multiplier for this variant (e.g., 0.7 for cost_conscious)

    Returns:
        Budget-adjusted cost multiplier
    """
    # Estimate baseline costs for a mid-tier trip (per day)
    baseline_lodging_per_night = 15000  # $150/night
    baseline_attraction_per_day = 8000  # $80 in attractions per day (2 attractions @ $40 each)
    baseline_daily_spend = 8000  # $80 for meals and miscellaneous

    # Calculate per-day baseline (excluding flight which is one-time cost)
    baseline_per_day = (
        baseline_lodging_per_night +
        baseline_attraction_per_day +
        baseline_daily_spend
    )  # Total: $310/day

    # Calculate per-day budget
    budget_per_day = intent.budget_usd_cents / max(trip_days, 1)

    # Calculate budget ratio (how much per-day budget vs per-day baseline)
    budget_ratio = budget_per_day / max(baseline_per_day, 1)

    # Adjust multiplier based on budget pressure
    # Lower budget_ratio → tighter budget → need lower multiplier
    if budget_ratio < 0.8:
        # Very tight budget (< 80% of baseline) - aggressive cost reduction
        adjustment = 0.6
    elif budget_ratio < 1.0:
        # Below baseline (80-100%) - moderate reduction
        adjustment = 0.8
    elif budget_ratio < 1.5:
        # Comfortable budget (100-150%) - normal costs
        adjustment = 1.0
    elif budget_ratio < 2.0:
        # Good budget (150-200%) - can afford slightly more
        adjustment = 1.1
    elif budget_ratio < 3.0:
        # Generous budget (200-300%) - can splurge more
        adjustment = 1.25
    elif budget_ratio < 4.0:
        # Very generous budget (300-400%) - premium options
        adjustment = 1.35
    else:
        # Luxury budget (400%+) - max multiplier for best options
        adjustment = 1.45

    # Apply adjustment to base multiplier
    result = base_multiplier * adjustment

    # Clamp between reasonable bounds (0.5x to 1.5x)
    return max(0.5, min(result, 1.5))


def _build_cost_conscious_plan(intent: IntentV1, trip_days: int, rng: random.Random) -> PlanV1:
    """Build a cost-conscious plan emphasizing budget-friendly options."""
    base_multiplier = 0.7
    adjusted_multiplier = _calculate_budget_multiplier(intent, trip_days, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=0.8,  # Slightly fewer activities
        variant_name="cost_conscious"
    )


def _build_convenience_plan(intent: IntentV1, trip_days: int, rng: random.Random) -> PlanV1:
    """Build a convenience-focused plan emphasizing shorter travel times."""
    base_multiplier = 1.0
    adjusted_multiplier = _calculate_budget_multiplier(intent, trip_days, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=1.0,  # Normal activity count
        variant_name="convenience"
    )


def _build_experience_plan(intent: IntentV1, trip_days: int, rng: random.Random) -> PlanV1:
    """Build an experience-focused plan with premium activities."""
    base_multiplier = 1.3
    adjusted_multiplier = _calculate_budget_multiplier(intent, trip_days, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=1.1,  # More activities
        variant_name="experience"
    )


def _build_relaxed_plan(intent: IntentV1, trip_days: int, rng: random.Random) -> PlanV1:
    """Build a relaxed plan with more free time."""
    base_multiplier = 0.9
    adjusted_multiplier = _calculate_budget_multiplier(intent, trip_days, base_multiplier)
    return _build_plan_variant(
        intent=intent,
        trip_days=trip_days,
        rng=rng,
        cost_multiplier=adjusted_multiplier,
        activity_density=0.6,  # Fewer activities, more free time
        variant_name="relaxed"
    )


def _build_plan_variant(
    intent: IntentV1,
    trip_days: int,
    rng: random.Random,
    cost_multiplier: float,
    activity_density: float,
    variant_name: str,
) -> PlanV1:
    """Build a plan variant with specific characteristics."""
    start_date = intent.date_window.start
    days: list[DayPlan] = []

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
                    cost_usd_cents=int(75000 * cost_multiplier),  # Estimated $750 base
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
                    cost_usd_cents=int(75000 * cost_multiplier),  # Estimated $750 base
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
        base_activities = int(activity_density * 2)  # 0-3 activities per day
        activities_to_add = max(0, base_activities - len(slots))

        # Generate morning activities
        if activities_to_add > 0 and not _has_slot_in_timerange(slots, time(8, 0), time(12, 0)):
            morning_choice = _create_activity_choice(
                day_offset, "morning", rng, cost_multiplier, variant_name, intent
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
                day_offset, "afternoon", rng, cost_multiplier, variant_name, intent
            )
            slots.append(Slot(
                window=TimeWindow(start=time(14, 0), end=time(17, 0)),
                choices=[afternoon_choice],
                locked=False,
            ))
            activities_to_add -= 1

        # Generate evening activities for higher activity density
        if (activities_to_add > 0 and activity_density > 0.8 and
            not _has_slot_in_timerange(slots, time(18, 0), time(22, 0))):
            evening_choice = _create_activity_choice(
                day_offset, "evening", rng, cost_multiplier, variant_name, intent
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
    # Determine tier based on budget
    budget_per_day = intent.budget_usd_cents / max(trip_days, 1)
    
    if budget_per_day < 15000:  # Less than $150/day
        lodging_tier = "budget"
        lodging_cost = int(7500 * cost_multiplier)  # ~$75/night
    elif budget_per_day < 30000:  # Less than $300/day
        lodging_tier = "mid"
        lodging_cost = int(15000 * cost_multiplier)  # ~$150/night
    else:
        lodging_tier = "luxury"
        lodging_cost = int(35000 * cost_multiplier)  # ~$350/night

    # Debug logging for lodging tier selection
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"Lodging selection: budget=${intent.budget_usd_cents/100:.0f}, days={trip_days}, "
        f"per_day=${budget_per_day/100:.0f}, tier={lodging_tier}, "
        f"cost_multiplier={cost_multiplier:.2f}, final_cost=${lodging_cost/100:.0f}/night"
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
    daily_spend = int(8000 * cost_multiplier)  # $80 base, adjusted by multiplier

    return PlanV1(
        days=days,
        assumptions=Assumptions(
            fx_rate_usd_eur=fx_rate,
            daily_spend_est_cents=daily_spend,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=rng.randint(0, 2**31 - 1),
    )


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
) -> Choice:
    """Create an activity choice for a specific time period."""

    # Determine activity type based on period and variant
    if period == "morning":
        kind = ChoiceKind.attraction
        base_cost = 3000
        themes = ["culture", "art"]
    elif period == "afternoon":
        kind = ChoiceKind.attraction
        base_cost = 4000
        themes = ["museums", "outdoor"]
    else:  # evening
        kind = ChoiceKind.meal
        base_cost = 2500
        themes = ["food", "dining"]

    # Apply user preferences to themes
    if intent.prefs.themes:
        themes = intent.prefs.themes[:2]  # Use first 2 user themes

    # Budget-aware activity type and cost selection
    trip_days = max((intent.date_window.end - intent.date_window.start).days, 1)
    budget_per_day = intent.budget_usd_cents / trip_days
    
    # Adjust both activity cost and type based on budget constraints
    if budget_per_day < 15000:  # Very tight budget (<$150/day)
        # Prioritize free or very cheap activities
        if period != "evening":  # For attractions
            base_cost = rng.choice([0, 500, 1000])  # Free to $10
            themes = ["park", "outdoor", "walking"] if "outdoor" in intent.prefs.themes or not intent.prefs.themes else themes
        else:  # For meals
            base_cost = 1500  # $15 meals
    elif budget_per_day < 30000:  # Moderate budget ($150-300/day)
        # Mix of free and reasonably priced activities
        if period != "evening":
            base_cost = rng.choice([1000, 2000, 3000])  # $10-30
        else:
            base_cost = 2500  # $25 meals
    else:  # Generous budget ($300+/day)
        # Can afford premium activities
        if period != "evening":
            base_cost = rng.choice([3000, 5000, 7000])  # $30-70
        else:
            base_cost = 4000  # $40+ meals

    # Apply cost multiplier and add randomness
    final_cost = int(base_cost * cost_multiplier * rng.uniform(0.8, 1.2))

    # Determine indoor/outdoor based on variant and randomness
    if variant_name == "experience":
        indoor = rng.choice([True, False, None])  # More varied
    elif variant_name == "relaxed":
        indoor = False if period != "evening" else True  # Outdoor during day
    else:
        indoor = rng.choice([True, None])  # Mostly indoor/unknown

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
