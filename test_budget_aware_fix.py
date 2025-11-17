#!/usr/bin/env python3

"""Test script to verify budget-aware behavior works correctly."""

from datetime import date
from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.adapters.flights import get_flights
from backend.app.adapters.lodging import get_lodging
from backend.app.adapters.events import get_attractions
from backend.app.models.common import Tier

def test_budget_aware_adapters():
    """Test that adapters respond appropriately to different budgets."""
    
    # Test scenarios: tight budget vs generous budget
    scenarios = [
        {
            "name": "Tight Budget ($1,000 for 5 days = $200/day)",
            "budget": 100_000,  # $1,000 total
            "days": 5
        },
        {
            "name": "Generous Budget ($5,000 for 5 days = $1,000/day)",
            "budget": 500_000,  # $5,000 total  
            "days": 5
        }
    ]
    
    print("=== Budget-Aware Adapter Testing ===\n")
    
    for scenario in scenarios:
        print(f"## {scenario['name']}")
        budget = scenario["budget"]
        
        # Create date window
        start_date = date(2025, 6, 1)
        end_date = date(2025, 6, 6)  # 5 days
        
        # Test flights
        print("\n### Flights:")
        flights = get_flights(
            origin="JFK",
            dest="Paris",  # Use Paris which has fixture data
            date_window=(start_date, end_date),
            budget_usd_cents=budget
        )
        
        for flight in flights[:3]:  # Show first 3
            print(f"  - {flight.flight_id}: ${flight.price_usd_cents/100:.0f}")
        
        # Test lodging
        print("\n### Lodging:")
        lodging = get_lodging(
            city="Paris",  # Use Paris which has fixture data
            checkin=start_date,
            checkout=end_date,
            budget_usd_cents=budget
        )
        
        for hotel in lodging[:3]:  # Show first 3
            print(f"  - {hotel.name} ({hotel.tier.value}): ${hotel.price_per_night_usd_cents/100:.0f}/night")
        
        # Test attractions
        print("\n### Attractions:")
        attractions = get_attractions(
            city="Paris",  # Use Paris which has fixture data
            themes=["art", "culture"],
            budget_usd_cents=budget
        )
        
        for attraction in attractions[:5]:  # Show first 5
            price = (attraction.est_price_usd_cents or 0) / 100
            print(f"  - {attraction.name}: ${price:.0f}")
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    test_budget_aware_adapters()
