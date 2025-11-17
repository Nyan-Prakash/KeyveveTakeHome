#!/usr/bin/env python3
"""Simple debug for transit injection logic."""

from datetime import date, time, datetime, timedelta

def test_time_gap_calculation():
    """Test the time gap calculation logic."""
    print("🔍 Testing Time Gap Calculation")
    print("=" * 40)
    
    # Simulate Rio scenario gaps
    scenarios = [
        ("Flight end → Lodging start", time(18, 0), time(22, 0)),  # 4 hour gap
        ("Attraction end → Lodging start", time(12, 0), time(22, 0)),  # 10 hour gap
    ]
    
    for desc, end_time, start_time in scenarios:
        # Calculate available time like our algorithm does
        buffer_minutes = 15  # Default buffer
        
        # Transit starts after buffer from previous activity
        transit_start_dt = datetime.combine(datetime.today(), end_time) + timedelta(minutes=buffer_minutes)
        transit_start = transit_start_dt.time()
        
        # Calculate max available time for transit
        def time_diff_minutes(start_t, end_t):
            start_dt = datetime.combine(datetime.today(), start_t)
            end_dt = datetime.combine(datetime.today(), end_t)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            return int((end_dt - start_dt).total_seconds() / 60)
        
        max_available_time = time_diff_minutes(transit_start, start_time) - buffer_minutes
        
        print(f"\n{desc}:")
        print(f"  Previous activity ends: {end_time}")
        print(f"  Next activity starts: {start_time}")
        print(f"  Transit can start: {transit_start} (after {buffer_minutes}min buffer)")
        print(f"  Available time for transit: {max_available_time} minutes")
        print(f"  Sufficient time? {'✅ Yes' if max_available_time > 5 else '❌ No'}")

def test_budget_transit_selection():
    """Test budget-aware transit mode selection."""
    print("\n🚗 Testing Budget-Aware Transit Selection")
    print("=" * 45)
    
    # Test different budget scenarios
    scenarios = [
        ("Low budget ($500)", 50000),
        ("Medium budget ($1500)", 150000), 
        ("High budget ($5000)", 500000),
    ]
    
    distance_km = 5.0  # 5km distance
    
    for desc, budget_cents in scenarios:
        trip_days = 4
        budget_per_day = budget_cents / trip_days
        
        print(f"\n{desc} (${budget_cents/100:.0f} total, ${budget_per_day/100:.0f}/day):")
        
        # Budget thresholds from our algorithm
        BUDGET_TIGHT = 15000    
        BUDGET_MODERATE = 30000 
        
        if budget_per_day < BUDGET_TIGHT:
            if distance_km <= 2.0:
                mode = "walk"
                cost = 0
            else:
                mode = "metro"
                cost = 200
        elif budget_per_day < BUDGET_MODERATE:
            if distance_km > 5.0:
                mode = "taxi"
                cost = 300 + int(25 * 150)  # base + duration estimate
            else:
                mode = "metro"
                cost = 200
        else:
            if distance_km <= 0.8:
                mode = "walk"
                cost = 0
            else:
                mode = "taxi" 
                cost = 300 + int(25 * 150)
        
        print(f"  Selected: {mode} (${cost/100:.2f})")

if __name__ == "__main__":
    test_time_gap_calculation()
    test_budget_transit_selection()
    print("\n✅ Debug tests completed!")
