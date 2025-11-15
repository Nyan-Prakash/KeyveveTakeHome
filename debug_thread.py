#!/usr/bin/env python3
"""Test the background thread execution directly."""

import threading
import time
from datetime import date
from uuid import UUID

from backend.app.db.session import get_session_factory
from backend.app.graph.runner import _execute_graph
from backend.app.models.intent import DateWindow, IntentV1, Preferences


def test_background_execution():
    """Test the _execute_graph function directly."""
    print("Testing _execute_graph function directly...")
    
    # Create test intent
    intent = IntentV1(
        city="Tokyo",
        date_window=DateWindow(
            start=date(2025, 8, 1),
            end=date(2025, 8, 5),
            tz="Asia/Tokyo"
        ),
        budget_usd_cents=400000,
        airports=["NRT"],
        prefs=Preferences(
            kid_friendly=False,
            themes=["culture"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    # Test parameters
    run_id = UUID("12345678-1234-1234-1234-123456789abc")
    org_id = UUID("00000000-0000-0000-0000-000000000001")
    user_id = UUID("00000000-0000-0000-0000-000000000002")
    trace_id = "test-trace-123"
    seed = 42
    
    # Create agent run record first
    factory = get_session_factory()
    session = factory()
    
    try:
        from backend.app.db.models.agent_run import AgentRun
        from datetime import UTC, datetime
        
        # Create test agent run
        agent_run = AgentRun(
            run_id=run_id,
            org_id=org_id, 
            user_id=user_id,
            intent=intent.model_dump(mode="json"),
            status="running",
            trace_id=trace_id,
            created_at=datetime.now(UTC),
        )
        session.add(agent_run)
        session.commit()
        print(f"✓ Created agent run: {run_id}")
        
    finally:
        session.close()
    
    print("Testing direct function call (synchronous)...")
    try:
        start_time = time.time()
        _execute_graph(run_id, org_id, user_id, trace_id, intent, seed)
        end_time = time.time()
        print(f"✓ Direct call completed in {end_time - start_time:.2f}s")
        
        # Check final status
        session = factory()
        try:
            from sqlalchemy import text
            uuid_format = str(run_id).replace('-', '')
            status = session.execute(text(
                "SELECT status FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": uuid_format}).scalar()
            print(f"✓ Final status: {status}")
            
        finally:
            session.close()
            
        return True
        
    except Exception as e:
        print(f"❌ Direct call failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_threaded_execution():
    """Test the same function in a thread."""
    print("\nTesting _execute_graph in a thread...")
    
    # Create test intent
    intent = IntentV1(
        city="London", 
        date_window=DateWindow(
            start=date(2025, 9, 1),
            end=date(2025, 9, 5),
            tz="Europe/London"
        ),
        budget_usd_cents=350000,
        airports=["LHR"],
        prefs=Preferences(
            kid_friendly=True,
            themes=["history"],
            avoid_overnight=False,
            locked_slots=[]
        )
    )
    
    # Test parameters
    run_id = UUID("87654321-4321-4321-4321-123456789abc")
    org_id = UUID("00000000-0000-0000-0000-000000000001")
    user_id = UUID("00000000-0000-0000-0000-000000000002") 
    trace_id = "test-trace-456"
    seed = 42
    
    # Create agent run record first
    factory = get_session_factory()
    session = factory()
    
    try:
        from backend.app.db.models.agent_run import AgentRun
        from datetime import UTC, datetime
        
        # Create test agent run
        agent_run = AgentRun(
            run_id=run_id,
            org_id=org_id,
            user_id=user_id,
            intent=intent.model_dump(mode="json"),
            status="running",
            trace_id=trace_id,
            created_at=datetime.now(UTC),
        )
        session.add(agent_run)
        session.commit()
        print(f"✓ Created agent run: {run_id}")
        
    finally:
        session.close()
    
    # Thread completion tracking
    thread_completed = threading.Event()
    thread_error = None
    
    def wrapped_execute():
        try:
            _execute_graph(run_id, org_id, user_id, trace_id, intent, seed)
            thread_completed.set()
        except Exception as e:
            nonlocal thread_error
            thread_error = e
            thread_completed.set()
    
    print("Starting background thread...")
    start_time = time.time()
    thread = threading.Thread(target=wrapped_execute, daemon=False)
    thread.start()
    
    # Wait for completion with timeout
    if thread_completed.wait(timeout=15):
        end_time = time.time()
        if thread_error:
            print(f"❌ Thread failed: {thread_error}")
            import traceback
            traceback.print_exception(type(thread_error), thread_error, thread_error.__traceback__)
            return False
        else:
            print(f"✓ Thread completed in {end_time - start_time:.2f}s")
            
            # Check final status
            session = factory()
            try:
                from sqlalchemy import text
                uuid_format = str(run_id).replace('-', '')
                status = session.execute(text(
                    "SELECT status FROM agent_run WHERE run_id = :run_id"
                ), {"run_id": uuid_format}).scalar()
                print(f"✓ Final status: {status}")
                
            finally:
                session.close()
                
            return True
    else:
        print("❌ Thread did not complete within 15 seconds")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DEBUG: Background Thread Analysis") 
    print("=" * 60)
    
    direct_ok = test_background_execution()
    
    if direct_ok:
        threaded_ok = test_threaded_execution() 
        
        if threaded_ok:
            print("\n🎉 Both direct and threaded execution work!")
        else:
            print("\n⚠️  Threaded execution failed")
    else:
        print("\n❌ Direct execution failed")
