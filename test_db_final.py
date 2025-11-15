#!/usr/bin/env python3
"""Final database verification - step by step."""

from backend.app.db.session import get_session_factory
from backend.app.db.models.agent_run import AgentRun
from backend.app.models.intent import IntentV1, DateWindow, Preferences
from backend.app.graph import start_run
from datetime import date, datetime, UTC
from uuid import UUID, uuid4
from sqlalchemy import text
import json
import time


def test_everything_step_by_step():
    """Test every step of the database integration."""
    print("=== STEP-BY-STEP DATABASE VERIFICATION ===\n")
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Step 1: Verify basic database connectivity
        print("STEP 1: Basic database connectivity")
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
        print("✓ Database connection working\n")
        
        # Step 2: Verify test org and user exist
        print("STEP 2: Verify test data exists")
        org_count = session.execute(text("SELECT COUNT(*) FROM org")).scalar()
        user_count = session.execute(text("SELECT COUNT(*) FROM user")).scalar()
        print(f"✓ Found {org_count} orgs and {user_count} users\n")
        
        # Step 3: Test direct agent run creation
        print("STEP 3: Direct agent run creation")
        
        test_intent = {
            "city": "Direct Test",
            "budget_usd_cents": 100000,
            "date_window": {"start": "2025-06-01", "end": "2025-06-05", "tz": "UTC"},
            "airports": ["TEST"],
            "prefs": {"kid_friendly": False, "themes": [], "avoid_overnight": False, "locked_slots": []}
        }
        
        direct_run_id = str(uuid4())
        session.execute(text("""
            INSERT INTO agent_run (run_id, org_id, user_id, intent, status, trace_id, created_at)
            VALUES (:run_id, :org_id, :user_id, :intent, :status, :trace_id, :created_at)
        """), {
            "run_id": direct_run_id,
            "org_id": "00000000000000000000000000000001",  # Note: no hyphens to match stored format
            "user_id": "00000000000000000000000000000002",
            "intent": json.dumps(test_intent),
            "status": "test_direct",
            "trace_id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat()
        })
        session.commit()
        
        # Verify it was stored
        result = session.execute(text(
            "SELECT status FROM agent_run WHERE run_id = :run_id"
        ), {"run_id": direct_run_id}).scalar()
        
        print(f"✓ Direct creation: {direct_run_id} -> status: {result}\n")
        
        # Step 4: Test ORM creation
        print("STEP 4: ORM-based agent run creation")
        
        test_intent_obj = IntentV1(
            city="ORM Test",
            date_window=DateWindow(start=date(2025, 6, 1), end=date(2025, 6, 5), tz="UTC"),
            budget_usd_cents=150000,
            airports=["ORM"],
            prefs=Preferences(kid_friendly=False, themes=["test"], avoid_overnight=False, locked_slots=[])
        )
        
        orm_run = AgentRun(
            run_id=uuid4(),
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=test_intent_obj.model_dump(mode="json"),
            status="test_orm",
            trace_id=str(uuid4()),
            created_at=datetime.now(UTC),
        )
        
        session.add(orm_run)
        session.commit()
        session.refresh(orm_run)
        
        print(f"✓ ORM creation: {orm_run.run_id} -> status: {orm_run.status}")
        
        # Try to query it back
        orm_check = session.execute(text(
            "SELECT status FROM agent_run WHERE run_id = :run_id"
        ), {"run_id": str(orm_run.run_id)}).scalar()
        
        print(f"✓ ORM verification: {orm_check}\n")
        
        # Step 5: Test start_run function
        print("STEP 5: Testing start_run function")
        
        langgraph_intent = IntentV1(
            city="LangGraph Test",
            date_window=DateWindow(start=date(2025, 6, 1), end=date(2025, 6, 5), tz="UTC"),
            budget_usd_cents=200000,
            airports=["LG"],
            prefs=Preferences(kid_friendly=False, themes=["langgraph"], avoid_overnight=False, locked_slots=[])
        )
        
        start_run_id = start_run(
            session=session,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent=langgraph_intent,
            seed=42
        )
        
        print(f"✓ start_run returned: {start_run_id} (type: {type(start_run_id)})")
        
        # Give background processing time
        print("   Waiting 3 seconds for background processing...")
        time.sleep(3)
        
        # Check different UUID formats
        uuid_formats = [
            ("String with hyphens", str(start_run_id)),
            ("String without hyphens", str(start_run_id).replace('-', '')),
        ]
        
        found = False
        for format_name, uuid_str in uuid_formats:
            result = session.execute(text(
                "SELECT status, intent FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": uuid_str}).fetchone()
            
            if result:
                status, intent_json = result
                intent_data = json.loads(intent_json)
                print(f"✓ Found with {format_name}: status={status}, city={intent_data['city']}")
                found = True
                break
            else:
                print(f"   ❌ Not found with {format_name}")
        
        if not found:
            print("   Checking all recent runs...")
            recent = session.execute(text(
                "SELECT run_id, status, intent FROM agent_run ORDER BY created_at DESC LIMIT 3"
            )).fetchall()
            
            for run_id, status, intent in recent:
                intent_data = json.loads(intent)
                print(f"   - {run_id}: {status} ({intent_data['city']})")
        
        print(f"\nStep 5 result: {'✓ SUCCESS' if found else '❌ FAILED'}\n")
        
        # Step 6: Summary
        print("STEP 6: Summary")
        total_runs = session.execute(text("SELECT COUNT(*) FROM agent_run")).scalar()
        print(f"✓ Total agent runs in database: {total_runs}")
        
        success = found
        print(f"\n{'🎉 ALL TESTS PASSED' if success else '⚠️  SOME TESTS FAILED'}")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    success = test_everything_step_by_step()
    exit(0 if success else 1)
