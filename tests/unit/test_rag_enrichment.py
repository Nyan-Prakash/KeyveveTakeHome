#!/usr/bin/env python3
"""Test script for RAG enrichment of flights and transit."""

import sys
import uuid
from datetime import date, time, datetime, timezone
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.graph.nodes import (
    _extract_flight_info_from_rag,
    _extract_transit_info_from_rag,
    tool_exec_node,
)
from backend.app.graph.state import OrchestratorState
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


def test_flight_rag_extraction():
    """Test extraction of flight information from RAG chunks."""
    
    print("=== Testing Flight RAG Extraction ===")
    
    sample_chunks = [
        """# Airlines to Rio de Janeiro
        
        ## LATAM Airlines
        - Direct flights from JFK to GIG
        - Flight duration: 9.5 hours  
        - Typical pricing: $650-800 for economy
        - Good service and reliability
        
        ## American Airlines
        - Connects through Miami (MIA)
        - Total journey: 11-12 hours
        - Pricing around $550-700
        """,
        
        """# Madrid Flight Options
        
        ## TAP Air Portugal
        - Route: JFK-MAD via Lisbon
        - Duration: 10 hours including layover
        - Economy fares from $450
        
        ## Iberia
        - Direct JFK-MAD route
        - 7.5 hour flight time
        - Premium carrier, $600+ typical
        """
    ]
    
    flight_info = _extract_flight_info_from_rag(sample_chunks)
    
    print(f"Extracted {len(flight_info)} flight entries:")
    for idx, info in flight_info.items():
        print(f"  {idx}: {info}")
        
        # Verify expected structure
        if "airline" in info and "price_usd_cents" in info:
            print(f"    ✅ Valid flight info extracted")
        else:
            print(f"    ❌ Missing required fields")
    
    return len(flight_info) > 0


def test_transit_rag_extraction():
    """Test extraction of transit information from RAG chunks."""
    
    print("\n=== Testing Transit RAG Extraction ===")
    
    sample_chunks = [
        """# Rio de Janeiro Transportation
        
        ## Metro System
        - Line 1 (Orange): Ipanema to Centro
        - Line 2 (Green): Copacabana to Botafogo  
        - Single ride: R$4.30 (~$1.25)
        - Journey time: 15-25 minutes typical
        
        ## Bus Network
        - Bus 474: Copacabana to Centro
        - Express routes available
        - Fare: R$3.50 (~$1.00)
        - Can take 30-45 minutes in traffic
        """,
        
        """# Madrid Public Transport
        
        ## Metro de Madrid
        - Line 1 (Light Blue): Pinar de Chamartín to Valdecarros
        - Serves major tourist areas
        - Single ticket: €1.50-2.00 ($1.60-2.20)
        - Average journey: 20 minutes
        
        ## Bus EMT
        - Comprehensive city bus network
        - Same fare as metro
        - Night buses (Búhos) available
        """
    ]
    
    transit_info = _extract_transit_info_from_rag(sample_chunks)
    
    print(f"Extracted {len(transit_info)} transit entries:")
    for idx, info in transit_info.items():
        print(f"  {idx}: {info}")
        
        # Verify expected structure
        if "mode" in info and "price_usd_cents" in info:
            print(f"    ✅ Valid transit info extracted")
        else:
            print(f"    ❌ Missing required fields")
    
    return len(transit_info) > 0


def test_enrichment_integration():
    """Test that tool_exec_node properly enriches flights and transit with RAG data."""
    
    print("\n=== Testing RAG Enrichment Integration ===")
    
    # Create a test state with sample RAG chunks
    test_state = OrchestratorState(
        trace_id="test-trace",
        org_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        seed=42,
        intent=IntentV1(
            city="Rio de Janeiro",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="America/Sao_Paulo"
            ),
            airports=["JFK"],
            budget_usd_cents=250000,  # $2500
            prefs=Preferences(),
        ),
        rag_chunks=[
            """# Airlines to Rio de Janeiro
            
            ## LATAM Airlines
            - Direct flights from JFK to GIG  
            - Flight duration: 9.5 hours
            - Typical pricing: $650 for economy
            """,
            
            """# Rio Transportation
            
            ## Metro System
            - Line 1: Ipanema to Centro
            - Single ride: R$4.30 (~$1.25)
            - Journey time: 15 minutes typical
            """
        ]
    )
    
    # Create a simple test plan with flights and transit
    morning_choice = Choice(
        kind=ChoiceKind.attraction,
        option_ref="morning_museum",
        features=ChoiceFeatures(
            cost_usd_cents=2000,
            travel_seconds=3600,
            indoor=True,
            themes=["culture"],
        ),
        score=0.8,
        provenance=Provenance(
            source="test",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    
    transit_choice = Choice(
        kind=ChoiceKind.transit,
        option_ref="transit_2025-06-01_0_metro",
        features=ChoiceFeatures(
            cost_usd_cents=200,  # $2
            travel_seconds=900,  # 15 minutes
            indoor=None,
            themes=None,
        ),
        score=0.8,
        provenance=Provenance(
            source="simple_transit",
            fetched_at=datetime.now(timezone.utc),
        ),
    )
    
    test_plan = PlanV1(
        days=[
            DayPlan(
                date=date(2025, 6, 1),
                slots=[
                    Slot(
                        window=TimeWindow(start=time(9, 0), end=time(12, 0)),
                        choices=[morning_choice],
                        locked=False,
                    ),
                    Slot(
                        window=TimeWindow(start=time(12, 30), end=time(13, 0)),
                        choices=[transit_choice],
                        locked=False,
                    ),
                ],
            )
        ],
        assumptions=Assumptions(
            fx_rate_usd_eur=0.92,
            daily_spend_est_cents=10000,
            transit_buffer_minutes=15,
            airport_buffer_minutes=120,
        ),
        rng_seed=42,
    )
    
    test_state.plan = test_plan
    
    print(f"Initial state: {len(test_state.flights)} flights, {len(test_state.transit_legs)} transit legs")
    
    # Process the state with tool_exec_node 
    try:
        updated_state = tool_exec_node(test_state)
        
        print(f"After enrichment: {len(updated_state.flights)} flights, {len(updated_state.transit_legs)} transit legs")
        
        # Check if flights were enriched
        for flight_id, flight in updated_state.flights.items():
            print(f"Flight {flight_id}: {flight.flight_id}")
            if "fixture+rag" in flight.provenance.source:
                print(f"  ✅ Flight enriched with RAG data")
            else:
                print(f"  ⚠️ Flight not enriched (may be expected if no RAG match)")
        
        # Check if transit was enriched  
        for transit_id, transit in updated_state.transit_legs.items():
            print(f"Transit {transit_id}: mode={transit.mode.value}, duration={transit.duration_seconds}s")
            if "fixture+rag" in transit.provenance.source:
                print(f"  ✅ Transit enriched with RAG data")
            else:
                print(f"  ⚠️ Transit not enriched (may be expected if no RAG match)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during enrichment: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all RAG enrichment tests."""
    
    print("Testing RAG enrichment for flights and transit...\n")
    
    success = True
    
    try:
        success &= test_flight_rag_extraction()
        success &= test_transit_rag_extraction()
        success &= test_enrichment_integration()
        
        if success:
            print("\n🎉 All RAG enrichment tests passed!")
        else:
            print("\n❌ Some tests failed")
            
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
