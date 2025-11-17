#!/usr/bin/env python3
"""Test script for transit injection functionality."""

import sys
import uuid
from datetime import date, time, timedelta
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.models.common import ChoiceKind, Geo, TimeWindow
from backend.app.models.intent import DateWindow, IntentV1, Preferences
from backend.app.models.plan import (
    Assumptions,
    Choice,
    ChoiceFeatures,
    DayPlan,
    PlanV1,
    Slot,
)
from backend.app.models.common import Provenance
from backend.app.planning.transit_injector import inject_transit_between_activities
from datetime import datetime, timezone


def create_test_plan() -> PlanV1:
    """Create a simple test plan with morning and afternoon activities."""
    
    # Create test choices
    morning_choice = Choice(
        kind=ChoiceKind.attraction,
        option_ref="morning_museum",
        features=ChoiceFeatures(
            cost_usd_cents=2000,
            travel_seconds=1800,
            indoor=True,
            themes=["art", "culture"],
        ),
        score=0.8,
        provenance=Provenance(
            source="test",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    
    afternoon_choice = Choice(
        kind=ChoiceKind.attraction,
        option_ref="afternoon_park",
        features=ChoiceFeatures(
            cost_usd_cents=1000,
            travel_seconds=0,
            indoor=False,
            themes=["nature", "outdoor"],
        ),
        score=0.7,
        provenance=Provenance(
            source="test",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    
    # Create slots
    morning_slot = Slot(
        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
        choices=[morning_choice],
        locked=False,
    )
    
    afternoon_slot = Slot(
        window=TimeWindow(start=time(14, 0), end=time(17, 0)),
        choices=[afternoon_choice],
        locked=False,
    )
    
    # Create 4 day plans (minimum required)
    day_plans = []
    for i in range(4):
        day_date = date(2025, 6, 1) + timedelta(days=i)
        day_plan = DayPlan(
            date=day_date,
            slots=[morning_slot, afternoon_slot],
        )
        day_plans.append(day_plan)
    
    # Create plan
    plan = PlanV1(
        days=day_plans,
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=8000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )
    
    return plan


def create_test_intent(budget_cents: int = 250000) -> IntentV1:
    """Create a test intent with specified budget."""
    return IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris",
        ),
        budget_usd_cents=budget_cents,
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art", "culture"],
            avoid_overnight=False,
            locked_slots=[],
        ),
    )


def main():
    """Test transit injection."""
    print("🚗 Testing Transit Injection System")
    print("=" * 50)
    
    # Test with different budget scenarios
    test_budgets = [
        (50000, "Low budget ($500)"),
        (150000, "Medium budget ($1,500)"),
        (500000, "High budget ($5,000)"),
    ]
    
    for budget_cents, budget_desc in test_budgets:
        print(f"\n🧪 Testing {budget_desc}")
        print("-" * 40)
        
        # Create test data
        plan = create_test_plan()
        intent = create_test_intent(budget_cents)
        org_id = uuid.uuid4()
        
        # Inject transit
        try:
            enhanced_plan, messages = inject_transit_between_activities(plan, intent, org_id)
            
            print(f"✅ Transit injection successful!")
            
            # Show first day's transit options
            first_day = enhanced_plan.days[0]
            transit_slots = [slot for slot in first_day.slots if slot.choices[0].kind == ChoiceKind.transit]
            
            if transit_slots:
                transit_slot = transit_slots[0]
                transit_choice = transit_slot.choices[0]
                # Extract transit mode from option_ref
                mode = transit_choice.option_ref.split('_')[-1] if '_' in transit_choice.option_ref else "unknown"
                cost = transit_choice.features.cost_usd_cents / 100
                print(f"  Selected transit mode: {mode}")
                print(f"  Transit cost: ${cost:.2f}")
                
        except Exception as e:
            print(f"❌ Transit injection failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    print(f"\n🎉 All transit injection tests completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
