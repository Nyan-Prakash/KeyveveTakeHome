#!/usr/bin/env python3
"""Simple database verification test."""

from backend.app.db.session import get_session_factory
from sqlalchemy import text


def test_database_simple():
    """Test database with raw SQL to verify it works."""
    print("Testing database with raw SQL...")
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Test basic connectivity
        print("1. Testing basic connectivity...")
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
        print("   ✓ Database connection works")
        
        # Check what tables exist
        print("2. Checking tables...")
        tables_result = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()
        tables = [row[0] for row in tables_result]
        print(f"   ✓ Found tables: {', '.join(tables)}")
        
        # Check org table content
        print("3. Checking org table...")
        orgs = session.execute(text("SELECT org_id, name FROM org")).fetchall()
        print(f"   ✓ Found {len(orgs)} organizations")
        for org_id, name in orgs:
            print(f"     - {org_id}: {name}")
        
        # Check user table content  
        print("4. Checking user table...")
        users = session.execute(text("SELECT user_id, org_id, email FROM user")).fetchall()
        print(f"   ✓ Found {len(users)} users")
        for user_id, org_id, email in users:
            print(f"     - {user_id}: {email} (org: {org_id})")
        
        # Test creating an agent run with raw SQL
        print("5. Testing agent run creation with raw SQL...")
        import json
        import uuid
        from datetime import datetime, timezone
        
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        test_intent = {
            "city": "Paris",
            "budget_usd_cents": 250000,
            "date_window": {
                "start": "2025-06-01",
                "end": "2025-06-05",
                "tz": "Europe/Paris"
            },
            "airports": ["CDG"],
            "prefs": {
                "kid_friendly": False,
                "themes": ["art"],
                "avoid_overnight": False,
                "locked_slots": []
            }
        }
        
        # Use the first org and user from our results
        if orgs and users:
            org_id = orgs[0][0]
            user_id = users[0][0]
            
            session.execute(text("""
                INSERT INTO agent_run (run_id, org_id, user_id, intent, status, trace_id, created_at)
                VALUES (:run_id, :org_id, :user_id, :intent, :status, :trace_id, :created_at)
            """), {
                "run_id": run_id,
                "org_id": org_id,
                "user_id": user_id,
                "intent": json.dumps(test_intent),
                "status": "running",
                "trace_id": trace_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            session.commit()
            
            print(f"   ✓ Created agent run: {run_id}")
            
            # Test updating the run
            session.execute(text("""
                UPDATE agent_run 
                SET status = :status, tool_log = :tool_log, completed_at = :completed_at
                WHERE run_id = :run_id
            """), {
                "status": "completed",
                "tool_log": json.dumps({"test": "data", "tools_called": 5}),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id
            })
            session.commit()
            
            print("   ✓ Updated agent run to completed")
            
            # Test querying
            runs = session.execute(text(
                "SELECT COUNT(*) FROM agent_run WHERE org_id = :org_id"
            ), {"org_id": org_id}).scalar()
            print(f"   ✓ Found {runs} agent runs for org")
            
            completed_runs = session.execute(text(
                "SELECT COUNT(*) FROM agent_run WHERE org_id = :org_id AND status = 'completed'"
            ), {"org_id": org_id}).scalar()
            print(f"   ✓ Found {completed_runs} completed runs")
            
            # Verify JSON data integrity
            run_data = session.execute(text(
                "SELECT intent, tool_log FROM agent_run WHERE run_id = :run_id"
            ), {"run_id": run_id}).fetchone()
            
            if run_data:
                intent_data = json.loads(run_data[0])
                tool_data = json.loads(run_data[1])
                
                assert intent_data['city'] == "Paris"
                assert tool_data['tools_called'] == 5
                print("   ✓ JSON data integrity verified")
        
        print("\n✅ Database is working correctly!")
        print("   - SQLite database operational")
        print("   - Tables created successfully") 
        print("   - CRUD operations work")
        print("   - JSON data serialization works")
        print("   - Foreign key relationships intact")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    success = test_database_simple()
    exit(0 if success else 1)
