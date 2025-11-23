#!/usr/bin/env python3
"""Test vector storage and retrieval in PostgreSQL."""

import sys
from uuid import uuid4

from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.models.destination import Destination
from backend.app.db.models.org import Org
from backend.app.db.session import get_session_factory


def test_vector_storage():
    """Test that vectors can be stored and retrieved correctly."""
    print("\n" + "="*60)
    print("TESTING VECTOR STORAGE")
    print("="*60)
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Create test data
        org_id = uuid4()
        dest_id = uuid4()
        item_id = uuid4()
        
        print("\n1. Creating test organization and destination...")
        org = Org(org_id=org_id, name="Test Org")
        session.add(org)
        
        dest = Destination(
            dest_id=dest_id,
            org_id=org_id,
            city="Test City",
            country="Test Country",
            geo={"lat": 40.7128, "lon": -74.0060}  # Store as dict for JSONB
        )
        session.add(dest)
        
        print("2. Creating test knowledge item...")
        knowledge_item = KnowledgeItem(
            item_id=item_id,
            org_id=org_id,
            dest_id=dest_id,
            content="Test content"
        )
        session.add(knowledge_item)
        session.flush()
        
        print("3. Creating embedding with test vector...")
        test_vector = [0.1, 0.2, 0.3, 0.4, 0.5] * 307 + [0.1]  # 1536 dimensions
        
        embedding = Embedding(
            item_id=item_id,
            chunk_text="Test chunk",
            vector=test_vector
        )
        session.add(embedding)
        session.commit()
        
        print(f"   ✓ Stored vector with {len(test_vector)} dimensions")
        
        print("\n4. Retrieving embedding from database...")
        retrieved = session.query(Embedding).filter_by(item_id=item_id).first()
        
        if retrieved is None:
            print("   ❌ Failed to retrieve embedding")
            return False
            
        if retrieved.vector is None:
            print("   ❌ Retrieved vector is None")
            return False
            
        print(f"   ✓ Retrieved vector with {len(retrieved.vector)} dimensions")
        
        print("\n5. Verifying vector values...")
        if retrieved.vector[:5] == test_vector[:5]:
            print(f"   ✓ Vector values match: {retrieved.vector[:5]}")
        else:
            print(f"   ❌ Vector mismatch!")
            print(f"      Expected: {test_vector[:5]}")
            print(f"      Got: {retrieved.vector[:5]}")
            return False
            
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)
        print("\nVector storage is working correctly!")
        print("You can now:")
        print("  1. Start your backend server")
        print("  2. Upload knowledge documents")
        print("  3. View chunks in the UI")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            session.rollback()
        except:
            pass
        session.close()


if __name__ == "__main__":
    success = test_vector_storage()
    sys.exit(0 if success else 1)
