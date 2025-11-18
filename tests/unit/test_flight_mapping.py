#!/usr/bin/env python3

"""Simple test for flight choice features mapping"""

from datetime import date, time
from backend.app.adapters.flights import get_flights
from backend.app.adapters.feature_mapper import map_flight_to_features

def test_flight_feature_mapping():
    """Test that flight options properly map to choice features with cost"""
    
    print("=== Testing Flight Feature Mapping ===")
    
    # Get flights with budget
    flights = get_flights(
        origin="JFK",
        dest="Paris",
        date_window=(date(2025, 6, 1), date(2025, 6, 5)),
        budget_usd_cents=250000  # $2500 budget
    )
    
    print(f"Retrieved {len(flights)} flight options")
    
    # Test mapping to choice features
    for i, flight in enumerate(flights[:3]):  # Test first 3
        features = map_flight_to_features(flight)
        
        print(f"\nFlight {i+1}: {flight.flight_id}")
        print(f"  Original price: ${flight.price_usd_cents/100:.2f}")
        print(f"  Mapped cost: ${features.cost_usd_cents/100:.2f}")
        print(f"  Travel time: {features.travel_seconds/3600:.1f} hours")
        print(f"  Indoor: {features.indoor}")
        print(f"  Themes: {features.themes}")
        
        # Verify mapping is correct
        if flight.price_usd_cents == features.cost_usd_cents:
            print("  ✅ Cost mapping correct")
        else:
            print("  ❌ Cost mapping incorrect!")
            
        if flight.duration_seconds == features.travel_seconds:
            print("  ✅ Duration mapping correct")
        else:
            print("  ❌ Duration mapping incorrect!")

if __name__ == "__main__":
    test_flight_feature_mapping()
