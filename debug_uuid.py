#!/usr/bin/env python3
"""Debug UUID handling in database."""

from backend.app.db.session import get_session_factory
from sqlalchemy import text
from uuid import UUID
import json


def debug_uuid_handling():
    """Debug how UUIDs are being stored and retrieved."""
    print("Debugging UUID handling...")
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Check all agent runs in the database
        print("1. Checking all agent runs...")
        runs = session.execute(text(
            "SELECT run_id, status, created_at FROM agent_run ORDER BY created_at DESC"
        )).fetchall()
        
        print(f"   Found {len(runs)} agent runs:")
        for run_id, status, created_at in runs:
            print(f"     - {run_id} ({type(run_id).__name__}): {status} at {created_at}")
        
        # Test UUID conversion
        if runs:
            first_run_id = runs[0][0]
            print(f"\n2. Testing UUID queries with first run: {first_run_id}")
            
            # Try different query formats
            queries = [
                ("String query", "SELECT status FROM agent_run WHERE run_id = :run_id", {"run_id": str(first_run_id)}),
                ("Direct value", "SELECT status FROM agent_run WHERE run_id = :run_id", {"run_id": first_run_id}),
            ]
            
            if isinstance(first_run_id, str):
                try:
                    uuid_obj = UUID(first_run_id)
                    queries.append(("UUID object", "SELECT status FROM agent_run WHERE run_id = :run_id", {"run_id": uuid_obj}))
                except:
                    pass
            
            for name, query, params in queries:
                try:
                    result = session.execute(text(query), params).scalar()
                    print(f"   ✓ {name}: {result}")
                except Exception as e:
                    print(f"   ❌ {name}: {e}")
        
        # Test creating a new run directly
        print("\n3. Testing direct agent run creation...")
        from datetime import datetime, timezone
        from uuid import uuid4
        
        test_run_id = uuid4()
        test_intent = {
            "city": "Test City",
            "budget_usd_cents": 100000,
            "date_window": {"start": "2025-06-01", "end": "2025-06-05", "tz": "UTC"},
            "airports": ["TEST"],
            "prefs": {"kid_friendly": False, "themes": [], "avoid_overnight": False, "locked_slots": []}
        }
        
        session.execute(text("""
            INSERT INTO agent_run (run_id, org_id, user_id, intent, status, trace_id, created_at)
            VALUES (:run_id, :org_id, :user_id, :intent, :status, :trace_id, :created_at)
        """), {
            "run_id": str(test_run_id),
            "org_id": "00000000000000000000000000000001", 
            "user_id": "00000000000000000000000000000002",
            "intent": json.dumps(test_intent),
            "status": "test",
            "trace_id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        session.commit()
        
        print(f"   ✓ Created test run: {test_run_id}")
        
        # Try to query it back
        result = session.execute(text(
            "SELECT status FROM agent_run WHERE run_id = :run_id"
        ), {"run_id": str(test_run_id)}).scalar()
        
        print(f"   ✓ Query result: {result}")
        
        # Now test the start_run function
        print("\n4. Testing start_run function...")
        from backend.app.graph import start_run
        from backend.app.models.intent import IntentV1, DateWindow, Preferences
        from datetime import date
        
        test_intent_obj = IntentV1(
            city="Debug City",
            date_window=DateWindow(start=date(2025, 6, 1), end=date(2025, 6, 5), tz="UTC"),
            budget_usd_cents=150000,
            airports=["DBG"],
            prefs=Preferences(kid_friendly=False, themes=["debug"], avoid_overnight=False, locked_slots=[])
        )
        
        # Use proper UUID objects
        org_uuid = UUID("00000000-0000-0000-0000-000000000001")
        user_uuid = UUID("00000000-0000-0000-0000-000000000002")
        
        run_id = start_run(
            session=session,
            org_id=org_uuid,
            user_id=user_uuid,
            intent=test_intent_obj,
            seed=42
        )
        
        print(f"   ✓ start_run returned: {run_id} ({type(run_id).__name__})")
        
        # Give it a moment to process
        import time
        time.sleep(2)
        
        # Try to find it
        result = session.execute(text(
            "SELECT status, intent FROM agent_run WHERE run_id = :run_id"
        ), {"run_id": str(run_id)}).fetchone()
        
        if result:
            status, intent = result
            print(f"   ✓ Found run with status: {status}")
            intent_data = json.loads(intent)
            print(f"   ✓ Intent city: {intent_data['city']}")
        else:
            print(f"   ❌ Run not found, trying different formats...")
            
            # Try without string conversion
            result2 = session.execute(text(
                "SELECT status FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": run_id}).fetchone()
            
            if result2:
                print(f"   ✓ Found with direct UUID: {result2[0]}")
            else:
                print("   ❌ Still not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    debug_uuid_handling()
