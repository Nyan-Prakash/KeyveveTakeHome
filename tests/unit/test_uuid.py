#!/usr/bin/env python3
"""Test UUID storage and retrieval directly."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.db.models.agent_run import AgentRun
from backend.app.db.session import get_session_factory


def test_uuid_operations():
    """Test UUID storage and retrieval."""
    print("Testing UUID operations...")
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Create a test run with a specific UUID
        test_uuid = uuid4()
        print(f"Original UUID: {test_uuid}")
        print(f"UUID string: {str(test_uuid)}")
        print(f"UUID without hyphens: {str(test_uuid).replace('-', '')}")
        
        # Create agent run
        agent_run = AgentRun(
            run_id=test_uuid,
            org_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            intent='{"test": true}',
            status="test",
            trace_id="test-trace",
            created_at=datetime.now(UTC),
        )
        
        session.add(agent_run)
        session.commit()
        print("✓ Agent run created")
        
        # Try to retrieve by UUID object
        retrieved_1 = session.get(AgentRun, test_uuid)
        print(f"Retrieved by UUID object: {retrieved_1 is not None}")
        
        # Try to retrieve by string
        retrieved_2 = session.get(AgentRun, str(test_uuid))
        print(f"Retrieved by UUID string: {retrieved_2 is not None}")
        
        # Try to retrieve by string without hyphens
        retrieved_3 = session.get(AgentRun, str(test_uuid).replace('-', ''))
        print(f"Retrieved by UUID string (no hyphens): {retrieved_3 is not None}")
        
        # Check what's actually stored in the database
        from sqlalchemy import text
        stored_value = session.execute(text(
            "SELECT run_id FROM agent_run WHERE trace_id = 'test-trace'"
        )).scalar()
        print(f"Actual stored value: '{stored_value}'")
        
        # Try updating the record
        if retrieved_3:  # Use the working retrieval method
            print("Attempting to update record...")
            retrieved_3.status = "updated"
            session.commit()
            print("✓ Update successful")
        else:
            print("❌ Could not retrieve record for update")
            
        return retrieved_3 is not None
        
    finally:
        session.close()


if __name__ == "__main__":
    if test_uuid_operations():
        print("\n✅ UUID operations work correctly")
    else:
        print("\n❌ UUID operations have issues")
