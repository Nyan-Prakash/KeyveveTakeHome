#!/usr/bin/env python3
"""Simple test for the LangGraph execution fix."""

import time
from datetime import date
from uuid import UUID

from backend.app.db.session import get_session_factory
from backend.app.graph import start_run
from backend.app.models.intent import DateWindow, IntentV1, Preferences


def test_fixed_execution():
    """Test that the LangGraph execution completes properly now."""
    print("Testing fixed LangGraph execution...")
    
    # Create test intent
    intent = IntentV1(
        city="Madrid",
        date_window=DateWindow(
            start=date(2025, 10, 1),
            end=date(2025, 10, 5),
            tz="Europe/Madrid"
        ),
        budget_usd_cents=280000,
        airports=["MAD"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["art", "food"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    factory = get_session_factory()
    session = factory()
    
    try:
        print("1. Starting run...")
        start_time = time.time()
        
        run_id = start_run(
            session=session,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=intent,
            seed=42
        )
        
        print(f"   ✓ Started run: {run_id}")
        
        # Monitor for completion
        from sqlalchemy import text
        uuid_format = str(run_id).replace('-', '')
        
        for i in range(15):  # Wait up to 15 seconds
            time.sleep(1)
            
            result = session.execute(text(
                "SELECT status, completed_at FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": uuid_format}).fetchone()
            
            if result:
                status, completed_at = result
                elapsed = time.time() - start_time
                print(f"   [{elapsed:.1f}s] Status: {status}")
                
                if status == "completed":
                    print(f"   ✅ Run completed successfully in {elapsed:.1f}s!")
                    print(f"   ✓ Completed at: {completed_at}")
                    return True
                elif status == "error":
                    print(f"   ❌ Run failed with error status")
                    return False
            else:
                print(f"   ⚠️  Run not found in database")
                return False
        
        print("   ⚠️  Run did not complete within 15 seconds")
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    if test_fixed_execution():
        print("\n🎉 LangGraph execution is now working correctly!")
    else:
        print("\n❌ LangGraph execution still has issues")
