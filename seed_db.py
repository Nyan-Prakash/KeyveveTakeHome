"""Seed database with test data for PR4."""

from datetime import UTC, datetime
from uuid import UUID

from backend.app.db.models.org import Org
from backend.app.db.models.user import User
from backend.app.db.session import get_session_factory

# Fixed UUIDs from the auth stub
TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000002")


def seed_test_data():
    """Create test org and user for PR4."""
    factory = get_session_factory()
    session = factory()

    try:
        # Check if org exists
        existing_org = session.get(Org, TEST_ORG_ID)
        if existing_org:
            print(f"✓ Test org already exists: {existing_org.org_id}")
        else:
            # Create test org
            org = Org(
                org_id=TEST_ORG_ID,
                name="Test Organization",
                created_at=datetime.now(UTC),
            )
            session.add(org)
            session.commit()
            print(f"✓ Created test org: {org.org_id}")

        # Check if user exists
        existing_user = session.get(User, TEST_USER_ID)
        if existing_user:
            print(f"✓ Test user already exists: {existing_user.user_id}")
        else:
            # Create test user
            user = User(
                user_id=TEST_USER_ID,
                org_id=TEST_ORG_ID,
                email="test@example.com",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$placeholder",
                created_at=datetime.now(UTC),
            )
            session.add(user)
            session.commit()
            print(f"✓ Created test user: {user.user_id}")

        print("\n✅ Database seeded successfully!")
        print(f"   Org ID:  {TEST_ORG_ID}")
        print(f"   User ID: {TEST_USER_ID}")

    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    seed_test_data()
