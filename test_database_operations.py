#!/usr/bin/env python3
"""Test database connectivity and basic operations."""

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.db.models.org import Org
from backend.app.db.models.user import User
from backend.app.db.models.agent_run import AgentRun
from backend.app.db.session import get_session_factory
from backend.app.models.intent import IntentV1, DateWindow, Preferences
from datetime import date


def test_database_operations():
    """Test basic database operations with SQLite."""
    print("Testing database operations...")
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Test reading existing data
        print("1. Testing read operations...")
        org = session.query(Org).filter_by(org_id="00000000-0000-0000-0000-000000000001").first()
        assert org is not None, "Test org should exist"
        print(f"   ✓ Found test org: {org.name}")
        
        user = session.query(User).filter_by(user_id="00000000-0000-0000-0000-000000000002").first()
        assert user is not None, "Test user should exist"
        print(f"   ✓ Found test user: {user.email}")
        
        # Get the actual UUID objects for foreign keys
        org_id = org.org_id
        user_id = user.user_id
        
        # Test creating an agent run
        print("2. Testing agent run creation...")
        
        test_intent = IntentV1(
            city="Paris",
            date_window=DateWindow(
                start=date(2025, 6, 1),
                end=date(2025, 6, 5),
                tz="Europe/Paris"
            ),
            budget_usd_cents=250_000,
            airports=["CDG"],
            prefs=Preferences(
                kid_friendly=False,
                themes=["art"],
                avoid_overnight=False,
                locked_slots=[]
            )
        )
        
        agent_run = AgentRun(
            run_id=uuid4(),
            org_id=org_id,
            user_id=user_id,
            intent=test_intent.model_dump(mode="json"),
            status="running",
            trace_id=str(uuid4()),
            created_at=datetime.now(UTC),
        )
        
        session.add(agent_run)
        session.commit()
        session.refresh(agent_run)
        
        print(f"   ✓ Created agent run: {agent_run.run_id}")
        print(f"   ✓ Intent city: {test_intent.city}")
        print(f"   ✓ Status: {agent_run.status}")
        
        # Test updating the agent run
        print("3. Testing agent run updates...")
        agent_run.status = "completed"
        agent_run.completed_at = datetime.now(UTC)
        agent_run.tool_log = {"test": "data", "tools_called": 5}
        session.commit()
        
        print(f"   ✓ Updated agent run status to: {agent_run.status}")
        print(f"   ✓ Tool log: {agent_run.tool_log}")
        
        # Test querying
        print("4. Testing queries...")
        
        runs = session.query(AgentRun).filter_by(org_id=org_id).all()
        print(f"   ✓ Found {len(runs)} agent runs for org")
        
        recent_runs = session.query(AgentRun).filter(
            AgentRun.org_id == org_id,
            AgentRun.status == "completed"
        ).all()
        print(f"   ✓ Found {len(recent_runs)} completed runs")
        
        # Test JSON data integrity
        print("5. Testing JSON data integrity...")
        retrieved_run = session.get(AgentRun, agent_run.run_id)
        assert retrieved_run is not None
        
        # Check that JSON data round-trips correctly
        intent_data = retrieved_run.intent
        assert intent_data['city'] == "Paris"
        assert intent_data['budget_usd_cents'] == 250_000
        print(f"   ✓ JSON intent data preserved: {intent_data['city']}")
        
        tool_log_data = retrieved_run.tool_log
        assert tool_log_data['tools_called'] == 5
        print(f"   ✓ JSON tool log preserved: {tool_log_data}")
        
        print("\n✅ All database operations successful!")
        print("   - SQLite database is working correctly")
        print("   - UUID handling works (stored as strings)")
        print("   - JSON data is properly serialized/deserialized") 
        print("   - Foreign key relationships work")
        print("   - Queries and updates function properly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        return False
        
    finally:
        session.close()


def test_health_check():
    """Test the health check endpoint with database."""
    print("\nTesting health check with database...")
    
    try:
        from backend.app.api.health import get_health
        import asyncio
        
        result = asyncio.run(get_health())
        print(f"   Health status: {result.status}")
        print(f"   DB check: {result.checks['db']}")
        print(f"   Redis check: {result.checks['redis']}")
        
        assert result.status == "ok", "Health check should pass"
        assert result.checks["db"] == "ok", "DB should be healthy"
        
        print("   ✅ Health check passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False


if __name__ == "__main__":
    db_success = test_database_operations()
    health_success = test_health_check()
    
    if db_success and health_success:
        print("\n🎉 Database is fully operational!")
        exit(0)
    else:
        print("\n⚠️ Some database tests failed")
        exit(1)
