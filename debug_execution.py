#!/usr/bin/env python3
"""Debug LangGraph execution to find where it's hanging."""

import sys
import time
from datetime import date
from uuid import UUID

from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.graph.runner import NODE_FUNCTIONS
from backend.app.graph.state import OrchestratorState
from backend.app.models.intent import DateWindow, IntentV1, Preferences


def debug_node_execution():
    """Test each node individually to find the hanging one."""
    print("Testing individual node execution...")
    
    # Create test intent
    intent = IntentV1(
        city="Paris",
        date_window=DateWindow(
            start=date(2025, 6, 1),
            end=date(2025, 6, 5),
            tz="Europe/Paris"
        ),
        budget_usd_cents=250000,
        airports=["CDG"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    # Create initial state
    state = OrchestratorState(
        trace_id="debug-trace",
        org_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        seed=42,
        intent=intent,
    )
    
    # Test each node individually
    node_sequence = [
        "intent",
        "planner", 
        "selector",
        "tool_exec",
        "verifier",
        "repair",
        "synth",
        "responder",
    ]
    
    for node_name in node_sequence:
        print(f"\n=== Testing {node_name} node ===")
        try:
            start_time = time.time()
            node_fn = NODE_FUNCTIONS[node_name]
            
            print(f"Calling {node_name}_node...")
            state = node_fn(state)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"✓ {node_name} completed in {duration:.2f}s")
            
        except Exception as e:
            print(f"❌ {node_name} failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print(f"\n✅ All nodes completed successfully!")
    print(f"Final state has plan: {state.plan is not None}")
    print(f"Final state has itinerary: {state.itinerary is not None}")
    return True


def debug_full_execution():
    """Test the full start_run process with detailed logging."""
    print("\n=== Testing full start_run execution ===")
    
    # Create test intent
    intent = IntentV1(
        city="Berlin",
        date_window=DateWindow(
            start=date(2025, 7, 1),
            end=date(2025, 7, 5),
            tz="Europe/Berlin"
        ),
        budget_usd_cents=300000,
        airports=["TXL"],
        prefs=Preferences(
            kid_friendly=True,
            themes=["culture", "history"], 
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    factory = get_session_factory()
    session = factory()
    
    try:
        print("Starting run...")
        start_time = time.time()
        
        run_id = start_run(
            session=session,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=intent,
            seed=42
        )
        
        print(f"Run started with ID: {run_id}")
        
        # Monitor status for 30 seconds
        from sqlalchemy import text
        
        for i in range(30):
            time.sleep(1)
            
            # Check status (try both UUID formats)
            uuid_formats = [str(run_id), str(run_id).replace('-', '')]
            status = None
            
            for uuid_format in uuid_formats:
                result = session.execute(text(
                    "SELECT status FROM agent_run WHERE run_id = :run_id"
                ), {"run_id": uuid_format}).scalar()
                
                if result:
                    status = result
                    break
            
            if status:
                elapsed = time.time() - start_time
                print(f"[{elapsed:.1f}s] Status: {status}")
                
                if status in ["completed", "error"]:
                    print(f"✅ Run finished after {elapsed:.1f}s with status: {status}")
                    return True
            else:
                print(f"[{i+1}s] No status found in database")
        
        print("⚠️  Run did not complete within 30 seconds")
        return False
        
    except Exception as e:
        print(f"❌ start_run failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("DEBUG: LangGraph Execution Analysis")
    print("=" * 60)
    
    # Test individual nodes first
    nodes_ok = debug_node_execution()
    
    if nodes_ok:
        print("\n" + "=" * 60)
        # Test full execution
        full_ok = debug_full_execution()
        
        if full_ok:
            print("\n🎉 All tests passed - system should be working!")
            sys.exit(0)
        else:
            print("\n⚠️  Full execution test failed")
            sys.exit(1)
    else:
        print("\n❌ Node execution test failed")
        sys.exit(1)
