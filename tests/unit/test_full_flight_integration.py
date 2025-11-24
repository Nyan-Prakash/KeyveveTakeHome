#!/usr/bin/env python3

"""Test end-to-end itinerary generation with proper flight costs"""

from datetime import date
from backend.app.models.intent import IntentV1, DateWindow, Preferences

def test_flight_cost_in_full_flow():
    """Test that flights have proper costs in the full planning flow"""
    
    # Create a test intent with budget
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
            themes=["art", "culture"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    # Test the graph nodes tool execution
    from backend.app.graph.state import OrchestratorState
    from backend.app.graph.nodes import tool_exec_node
    from uuid import uuid4
    
    # Create initial state with required fields
    state = OrchestratorState(
        trace_id="test-trace",
        org_id=uuid4(),
        user_id=uuid4(),
        seed=42,
        intent=intent,
        flights={},
        tool_call_counts={}
    )
    
    print("=== Testing Flight Integration in Full Flow ===")
    print(f"Intent: {intent.city}, Budget: ${intent.budget_usd_cents/100:.0f}")
    
    # Run the tool executor (which fetches flights)
    updated_state = tool_exec_node(state)
    
    print(f"Number of flights fetched: {len(updated_state.flights)}")
    for flight_id, flight in updated_state.flights.items():
        price_usd = flight.price_usd_cents / 100
        print(f"  {flight_id}: ${price_usd:.2f}")
    
    # Verify flights have non-zero costs
    non_zero_flights = [f for f in updated_state.flights.values() if f.price_usd_cents > 0]
    print(f"\nFlights with non-zero cost: {len(non_zero_flights)}/{len(updated_state.flights)}")
    
    if len(non_zero_flights) == len(updated_state.flights):
        print("✅ SUCCESS: All flights have proper pricing!")
    else:
        print("❌ FAIL: Some flights still have $0 cost")
    
    return updated_state.flights

if __name__ == "__main__":
    test_flight_cost_in_full_flow()
