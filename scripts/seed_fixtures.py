"""Seed fixtures script for local development and testing.

This script creates:
- A demo organization
- At least one user under that org
- Optionally, a sample destination and knowledge_item

Usage:
    python scripts/seed_fixtures.py
"""

from datetime import datetime
from uuid import uuid4

from backend.app.db.models.destination import Destination
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.models.org import Org
from backend.app.db.models.user import User
from backend.app.db.session import get_session_factory


def seed_demo_data() -> dict[str, str]:
    """
    Seed demo data into the database.

    Returns:
        Dictionary with created entity IDs for reference

    Example:
        result = seed_demo_data()
        print(f"Created org: {result['org_id']}")
        print(f"Created user: {result['user_id']}")
    """
    # Create session
    factory = get_session_factory()
    session = factory()

    try:
        # Check if demo org already exists
        existing_org = session.query(Org).filter_by(name="Demo Organization").first()

        if existing_org:
            print(f"Demo organization already exists (org_id={existing_org.org_id})")
            org = existing_org
        else:
            # Create demo organization
            org = Org(
                org_id=uuid4(),
                name="Demo Organization",
                created_at=datetime.now(datetime.UTC),
            )
            session.add(org)
            session.flush()
            print(f"Created organization: {org.name} (org_id={org.org_id})")

        # Check if demo user exists
        existing_user = (
            session.query(User)
            .filter_by(org_id=org.org_id, email="demo@example.com")
            .first()
        )

        if existing_user:
            print(f"Demo user already exists (user_id={existing_user.user_id})")
            user = existing_user
        else:
            # Create demo user
            # In a real scenario, password_hash would be Argon2id hash
            # For demo purposes, we use a placeholder
            user = User(
                user_id=uuid4(),
                org_id=org.org_id,
                email="demo@example.com",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$placeholder",  # Placeholder
                locked_until=None,
                created_at=datetime.now(datetime.UTC),
            )
            session.add(user)
            session.flush()
            print(f"Created user: {user.email} (user_id={user.user_id})")

        # Check if demo destination exists
        existing_dest = (
            session.query(Destination)
            .filter_by(org_id=org.org_id, city="Paris", country="France")
            .first()
        )

        if existing_dest:
            print(f"Demo destination already exists (dest_id={existing_dest.dest_id})")
            dest = existing_dest
        else:
            # Create demo destination
            dest = Destination(
                dest_id=uuid4(),
                org_id=org.org_id,
                city="Paris",
                country="France",
                geo={"lat": 48.8566, "lon": 2.3522},
                fixture_path="fixtures/paris_attractions.json",
                created_at=datetime.now(datetime.UTC),
            )
            session.add(dest)
            session.flush()
            print(
                f"Created destination: {dest.city}, {dest.country} (dest_id={dest.dest_id})"
            )

        # Check if demo knowledge item exists
        existing_knowledge = (
            session.query(KnowledgeItem)
            .filter_by(org_id=org.org_id, dest_id=dest.dest_id)
            .first()
        )

        if existing_knowledge:
            print(
                f"Demo knowledge item already exists (item_id={existing_knowledge.item_id})"
            )
            knowledge_item = existing_knowledge
        else:
            # Create demo knowledge item
            knowledge_item = KnowledgeItem(
                item_id=uuid4(),
                org_id=org.org_id,
                dest_id=dest.dest_id,
                content="The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris. "
                "It is open from 9:30 AM to 11:45 PM daily. Admission is approximately 25 EUR for adults.",
                item_metadata={
                    "source": "demo_seed",
                    "category": "attraction",
                    "venue": "Eiffel Tower",
                },
                created_at=datetime.now(datetime.UTC),
            )
            session.add(knowledge_item)
            session.flush()
            print(f"Created knowledge item (item_id={knowledge_item.item_id})")

        # Commit all changes
        session.commit()

        print("\n✅ Seed data created successfully!")

        return {
            "org_id": str(org.org_id),
            "org_name": org.name,
            "user_id": str(user.user_id),
            "user_email": user.email,
            "dest_id": str(dest.dest_id),
            "dest_name": f"{dest.city}, {dest.country}",
            "knowledge_item_id": str(knowledge_item.item_id),
        }

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error seeding data: {e}")
        raise
    finally:
        session.close()


def main() -> None:
    """Main entry point for seed script."""
    print("🌱 Seeding demo data...\n")

    result = seed_demo_data()

    print("\n📋 Summary:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
