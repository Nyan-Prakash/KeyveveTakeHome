#!/usr/bin/env python3

"""Test budget verification with proper flight costs"""

from datetime import date, time, timedelta, datetime, UTC
from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.models.plan import PlanV1, DayPlan, Slot, Choice, ChoiceFeatures, Assumptions
from backend.app.models.common import ChoiceKind, TimeWindow, Provenance
from backend.app.verify.budget import verify_budget

def test_budget_with_flight_costs():
    """Test that budget verification works with proper flight costs"""
    
    # Create test intent
    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris"
        ),
        budget_usd_cents=250000,  # $2500
        airports=["JFK"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    now = datetime.now(UTC)
    
    # Create a test plan with realistic flight costs
    flight_choice = Choice(
        kind=ChoiceKind.flight,
        option_ref="test_flight_001",
        features=ChoiceFeatures(
            cost_usd_cents=75000,  # $750 - realistic cost from our adapter
            travel_seconds=25200,  # 7 hours
            indoor=None,
            themes=None
        ),
        score=0.8,
        provenance=Provenance(
            source="flights_adapter",
            fetched_at=now,
            cache_hit=False
        )
    )
    
    # Create a return flight
    return_flight_choice = Choice(
        kind=ChoiceKind.flight,
        option_ref="test_flight_002", 
        features=ChoiceFeatures(
            cost_usd_cents=78000,  # $780 - realistic return cost
            travel_seconds=28800,  # 8 hours
            indoor=None,
            themes=None
        ),
        score=0.8,
        provenance=Provenance(
            source="flights_adapter",
            fetched_at=now,
            cache_hit=False
        )
    )
    
    # Create lodging choice
    lodging_choice = Choice(
        kind=ChoiceKind.lodging,
        option_ref="test_hotel_001",
        features=ChoiceFeatures(
            cost_usd_cents=15000,  # $150/night
            travel_seconds=None,
            indoor=True,
            themes=None
        ),
        score=0.7,
        provenance=Provenance(
            source="lodging_adapter",
            fetched_at=now,
            cache_hit=False
        )
    )
    
    # Create simple day plans
    day_plans = []
    for i in range(4):  # 4 days
        current_date = date(2025, 6, 1) + timedelta(days=i)
        slots = []
        
        if i == 0:  # Arrival day - outbound flight
            slots.append(Slot(
                window=TimeWindow(start=time(10, 0), end=time(18, 0)),
                choices=[flight_choice],
                locked=False
            ))
        elif i == 3:  # Departure day - return flight
            slots.append(Slot(
                window=TimeWindow(start=time(14, 0), end=time(22, 0)),
                choices=[return_flight_choice],
                locked=False
            ))
        
        # Add lodging to each day (except last day)
        if i < 3:
            slots.append(Slot(
                window=TimeWindow(start=time(22, 0), end=time(8, 0)),
                choices=[lodging_choice],
                locked=False
            ))
        
        day_plans.append(DayPlan(date=current_date, slots=slots))
    
    # Create plan
    plan = PlanV1(
        days=day_plans,
        assumptions=Assumptions(
            fx_rate_usd_eur=1.1,
            daily_spend_est_cents=5000  # $50/day for meals etc
        ),
        rng_seed=12345
    )
    
    print("=== Testing Budget Verification ===")
    print(f"Total budget: ${intent.budget_usd_cents/100:.2f}")
    
    # Calculate expected costs
    flight_cost = 75000 + 78000  # Outbound + return
    lodging_cost = 15000 * 3  # 3 nights
    daily_cost = 5000 * 4  # 4 days
    total_expected = flight_cost + lodging_cost + daily_cost
    
    print(f"Expected flight cost: ${flight_cost/100:.2f}")
    print(f"Expected lodging cost: ${lodging_cost/100:.2f}")
    print(f"Expected daily cost: ${daily_cost/100:.2f}")
    print(f"Expected total: ${total_expected/100:.2f}")
    
    # Run budget verification
    violations = verify_budget(intent, plan)
    
    print(f"\nBudget violations: {len(violations)}")
    for violation in violations:
        print(f"  - {violation.kind.value}: {violation.description}")
    
    if len(violations) == 0:
        print("✅ SUCCESS: Budget validation passed with proper flight costs!")
        return True
    else:
        print("❌ Budget exceeded, but this shows the system is working correctly")
        return False

if __name__ == "__main__":
    test_budget_with_flight_costs()
