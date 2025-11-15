#!/usr/bin/env python3
"""Test with debug prints in the _execute_graph function itself."""

import sys
import time
from datetime import UTC, datetime, date
from uuid import UUID

# Monkey patch the _execute_graph function to add debug prints
from backend.app.graph import runner
from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.models.intent import DateWindow, IntentV1, Preferences


# Save original function
original_execute_graph = runner._execute_graph

def debug_execute_graph(run_id, org_id, user_id, trace_id, intent, seed):
    """Wrapper around _execute_graph with debug prints."""
    print(f"🔍 DEBUG: _execute_graph started for run_id={run_id}")
    
    try:
        result = original_execute_graph(run_id, org_id, user_id, trace_id, intent, seed)
        print(f"🔍 DEBUG: _execute_graph completed successfully for run_id={run_id}")
        return result
    except Exception as e:
        print(f"🔍 DEBUG: _execute_graph failed for run_id={run_id}: {e}")
        import traceback
        traceback.print_exc()
        raise

# Monkey patch the function
runner._execute_graph = debug_execute_graph


def test_with_debug():
    """Test with debug logging in the _execute_graph function."""
    print("Testing with debug logging...")
    
    # Create test intent
    intent = IntentV1(
        city="Vienna",
        date_window=DateWindow(
            start=date(2025, 12, 1),
            end=date(2025, 12, 5),
            tz="Europe/Vienna"
        ),
        budget_usd_cents=290000,
        airports=["VIE"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["music"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    factory = get_session_factory()
    session = factory()
    
    try:
        print("Starting run...")
        run_id = start_run(
            session=session,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=intent,
            seed=42
        )
        
        print(f"Started run: {run_id}")
        
        # Wait a bit and check status
        for i in range(8):  # 8 seconds
            time.sleep(1)
            
            from sqlalchemy import text
            status = session.execute(text(
                "SELECT status FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": str(run_id).replace('-', '')}).scalar()
            
            if status:
                print(f"[{i+1}s] Status: {status}")
                if status in ["completed", "error"]:
                    return True
        
        print("No completion detected")
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    if test_with_debug():
        print("✅ Success!")
    else:
        print("❌ Still hanging")
