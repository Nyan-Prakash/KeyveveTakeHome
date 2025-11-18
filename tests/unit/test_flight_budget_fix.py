#!/usr/bin/env python3

"""Test the flight budget integration fix"""

from datetime import date
from backend.app.adapters.flights import get_flights

def test_flight_pricing():
    """Test that flights have proper pricing based on budget"""
    
    # Test with low budget - should return mostly budget flights
    print("=== LOW BUDGET TEST ($1000 total, 5 days) ===")
    low_budget_flights = get_flights(
        origin="JFK",
        dest="Paris",
        date_window=(date(2025, 6, 1), date(2025, 6, 5)),
        avoid_overnight=False,
        budget_usd_cents=100000  # $1000 total
    )
    
    print(f"Number of flights: {len(low_budget_flights)}")
    for i, flight in enumerate(low_budget_flights):
        price_usd = flight.price_usd_cents / 100
        print(f"  {i+1}. {flight.flight_id}: ${price_usd:.2f} (overnight: {flight.overnight})")
    
    # Test with high budget - should include premium flights  
    print("\n=== HIGH BUDGET TEST ($10000 total, 5 days) ===")
    high_budget_flights = get_flights(
        origin="JFK",
        dest="Paris", 
        date_window=(date(2025, 6, 1), date(2025, 6, 5)),
        avoid_overnight=False,
        budget_usd_cents=1000000  # $10000 total
    )
    
    print(f"Number of flights: {len(high_budget_flights)}")
    for i, flight in enumerate(high_budget_flights):
        price_usd = flight.price_usd_cents / 100
        print(f"  {i+1}. {flight.flight_id}: ${price_usd:.2f} (overnight: {flight.overnight})")
    
    # Test without budget - should include all tiers
    print("\n=== NO BUDGET TEST (all tiers) ===")
    all_flights = get_flights(
        origin="JFK",
        dest="Paris",
        date_window=(date(2025, 6, 1), date(2025, 6, 5)),
        avoid_overnight=False
    )
    
    print(f"Number of flights: {len(all_flights)}")
    for i, flight in enumerate(all_flights):
        price_usd = flight.price_usd_cents / 100
        print(f"  {i+1}. {flight.flight_id}: ${price_usd:.2f} (overnight: {flight.overnight})")

if __name__ == "__main__":
    test_flight_pricing()
