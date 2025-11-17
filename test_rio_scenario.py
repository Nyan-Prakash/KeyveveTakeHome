#!/usr/bin/env python3

"""Test Rio flight scenario specifically"""

from datetime import date
from backend.app.adapters.flights import get_flights

def test_rio_scenario():
    """Test the specific Rio scenario: 5 days in March with $3000 budget from JFK"""
    
    print("=== Testing Rio Scenario ===")
    print("Prompt: I want to visit Rio for 5 days in March 2 to March 7 with a $3000 budget departing from JFK")
    print()
    
    # Test the specific scenario
    flights = get_flights(
        origin="JFK",
        dest="Rio de Janeiro",  # Test with city name
        date_window=(date(2025, 3, 2), date(2025, 3, 7)),
        avoid_overnight=False,
        budget_usd_cents=300000  # $3000
    )
    
    print(f"Number of flights returned: {len(flights)}")
    
    if not flights:
        print("❌ NO FLIGHTS RETURNED! Let me debug...")
        
        # Test with airport code instead
        print("\n--- Testing with airport code instead of city name ---")
        flights_gig = get_flights(
            origin="JFK",
            dest="GIG",  # Rio airport code
            date_window=(date(2025, 3, 2), date(2025, 3, 7)),
            avoid_overnight=False,
            budget_usd_cents=300000
        )
        
        print(f"Number of flights with GIG: {len(flights_gig)}")
        
        if flights_gig:
            print("✅ Found flights when using airport code!")
            for i, flight in enumerate(flights_gig):
                print(f"  {i+1}. {flight.flight_id}: ${flight.price_usd_cents/100:.2f}")
        
        # Test budget calculation
        print("\n--- Testing budget calculation ---")
        budget_cents = 300000
        trip_days = 5
        budget_per_day = budget_cents / trip_days
        print(f"Budget per day: ${budget_per_day/100:.2f}")
        
        if budget_per_day < 15000:
            expected_tiers = ["budget"]
        elif budget_per_day < 30000:
            expected_tiers = ["budget", "mid"]
        else:
            expected_tiers = ["mid", "premium"]
        
        print(f"Expected tier preferences: {expected_tiers}")
        
        # Test the internal function directly
        print("\n--- Testing internal flight generation ---")
        from backend.app.adapters.flights import _generate_fixture_flights
        
        try:
            internal_flights = _generate_fixture_flights(
                origin="JFK",
                dest="GIG",
                flight_date=date(2025, 3, 2),
                avoid_overnight=False,
                tier_prefs=expected_tiers
            )
            print(f"Internal function returned {len(internal_flights)} flights")
            for flight in internal_flights:
                print(f"  {flight.flight_id}: ${flight.price_usd_cents/100:.2f}")
        except Exception as e:
            print(f"Error in internal function: {e}")
            
    else:
        print("✅ SUCCESS! Found flights:")
        for i, flight in enumerate(flights):
            print(f"  {i+1}. {flight.flight_id}: ${flight.price_usd_cents/100:.2f} (overnight: {flight.overnight})")
        
        # Check if costs are appropriate for budget
        budget_per_day = 300000 / 5  # $600/day
        print(f"\nBudget per day: ${budget_per_day/100:.2f}")
        
        avg_cost = sum(f.price_usd_cents for f in flights) / len(flights)
        print(f"Average flight cost: ${avg_cost/100:.2f}")
        
        if avg_cost <= budget_per_day:
            print("✅ Flight costs are budget-appropriate")
        else:
            print("ℹ️ Higher-tier flights (may be appropriate for generous budget)")

if __name__ == "__main__":
    test_rio_scenario()
