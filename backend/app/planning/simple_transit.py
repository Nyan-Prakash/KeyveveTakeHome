"""Simple transit injector for debugging - no external dependencies."""

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

from backend.app.models.common import ChoiceKind, Geo, TimeWindow, TransitMode
from backend.app.models.intent import IntentV1
from backend.app.models.plan import Choice, ChoiceFeatures, DayPlan, PlanV1, Slot
from backend.app.models.common import Provenance


def simple_inject_transit(plan: PlanV1, intent: IntentV1) -> PlanV1:
    """Simple transit injection without RAG dependencies."""
    
    enhanced_days = []
    
    for day_plan in plan.days:
        if not day_plan.slots:
            enhanced_days.append(day_plan)
            continue
        
        # Get all slots and sort by start time
        all_slots = sorted(day_plan.slots, key=lambda s: s.window.start)
        enhanced_slots = []
        
        for i, slot in enumerate(all_slots):
            # Add the original slot
            enhanced_slots.append(slot)
            
            # Add transit to next slot if available
            if i < len(all_slots) - 1:
                current_slot = slot
                next_slot = all_slots[i + 1]
                
                # Calculate time gap
                current_end = current_slot.window.end
                next_start = next_slot.window.start
                
                # Calculate available time (subtract buffer)
                buffer_minutes = 15
                end_dt = datetime.combine(datetime.today(), current_end)
                start_dt = datetime.combine(datetime.today(), next_start)
                gap_minutes = int((start_dt - end_dt).total_seconds() / 60)
                available_time = gap_minutes - (2 * buffer_minutes)  # Buffer on both ends
                
                if available_time > 10:  # Need at least 10 minutes for transit
                    # Create transit slot
                    transit_start_dt = end_dt + timedelta(minutes=buffer_minutes)
                    transit_start = transit_start_dt.time()
                    
                    # Use 30 minutes for transit or available time, whichever is less
                    transit_duration = min(30, available_time)
                    transit_end_dt = transit_start_dt + timedelta(minutes=transit_duration)
                    transit_end = transit_end_dt.time()
                    
                    # Budget-based mode selection
                    trip_days = len(plan.days)
                    budget_per_day = intent.budget_usd_cents / max(trip_days, 1)
                    
                    if budget_per_day < 20000:  # Less than $200/day
                        mode = TransitMode.metro
                        cost = 200  # $2
                    elif budget_per_day < 50000:  # Less than $500/day
                        mode = TransitMode.taxi
                        cost = 1000  # $10
                    else:
                        mode = TransitMode.taxi
                        cost = 1500  # $15
                    
                    transit_choice = Choice(
                        kind=ChoiceKind.transit,
                        option_ref=f"transit_{day_plan.date}_{i}_{mode.value}",
                        features=ChoiceFeatures(
                            cost_usd_cents=cost,
                            travel_seconds=transit_duration * 60,
                            indoor=None,
                            themes=None,
                        ),
                        score=0.8,
                        provenance=Provenance(
                            source="simple_transit",
                            fetched_at=datetime.now(UTC),
                        ),
                    )
                    
                    transit_slot = Slot(
                        window=TimeWindow(start=transit_start, end=transit_end),
                        choices=[transit_choice],
                        locked=False,
                    )
                    
                    enhanced_slots.append(transit_slot)
        
        enhanced_day = DayPlan(date=day_plan.date, slots=enhanced_slots)
        enhanced_days.append(enhanced_day)
    
    return PlanV1(
        days=enhanced_days,
        assumptions=plan.assumptions,
        rng_seed=plan.rng_seed,
    )
