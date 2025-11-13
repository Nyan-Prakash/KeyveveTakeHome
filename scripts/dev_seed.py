"""Development database seeding script.

Creates demo data for local development. Idempotent - safe to run multiple times.

Usage:
    python scripts/dev_seed.py
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.base import get_engine, get_session, get_session_factory
from backend.app.db.models import Destination, KnowledgeItem, Org, User


def seed_database() -> None:
    """Seed the database with demo data."""
    settings = get_settings()
    engine = get_engine(settings)
    session_factory = get_session_factory(engine)

    with get_session(session_factory) as session:
        # Check if org already exists
        org_stmt = select(Org).where(Org.name == "Demo Org")
        existing_org = session.execute(org_stmt).scalar_one_or_none()

        if existing_org:
            print(f"✓ Org 'Demo Org' already exists (ID: {existing_org.id})")
            org = existing_org
        else:
            # Create org
            org = Org(
                id=uuid4(),
                name="Demo Org",
                created_at=datetime.now(timezone.utc),
            )
            session.add(org)
            session.flush()
            print(f"✓ Created org 'Demo Org' (ID: {org.id})")

        # Check if user already exists
        user_stmt = select(User).where(
            User.org_id == org.id,
            User.email == "demo@keyveve.com"
        )
        existing_user = session.execute(user_stmt).scalar_one_or_none()

        if existing_user:
            print(f"✓ User 'demo@keyveve.com' already exists (ID: {existing_user.id})")
            user = existing_user
        else:
            # Create user
            user = User(
                id=uuid4(),
                org_id=org.id,
                email="demo@keyveve.com",
                hashed_password="$2b$12$dummy_hash_for_dev_only",  # Not a real hash
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            session.flush()
            print(f"✓ Created user 'demo@keyveve.com' (ID: {user.id})")

        # Check if destination already exists
        dest_stmt = select(Destination).where(
            Destination.org_id == org.id,
            Destination.slug == "paris"
        )
        existing_dest = session.execute(dest_stmt).scalar_one_or_none()

        if existing_dest:
            print(f"✓ Destination 'Paris' already exists (ID: {existing_dest.id})")
            destination = existing_dest
        else:
            # Create destination
            destination = Destination(
                id=uuid4(),
                org_id=org.id,
                name="Paris",
                slug="paris",
                created_at=datetime.now(timezone.utc),
            )
            session.add(destination)
            session.flush()
            print(f"✓ Created destination 'Paris' (ID: {destination.id})")

        # Check if knowledge items already exist
        ki_stmt = select(KnowledgeItem).where(
            KnowledgeItem.org_id == org.id,
            KnowledgeItem.destination_id == destination.id,
        )
        existing_items = session.execute(ki_stmt).scalars().all()

        if len(existing_items) >= 2:
            print(f"✓ Knowledge items already exist ({len(existing_items)} items)")
        else:
            # Create knowledge items
            ki1 = KnowledgeItem(
                id=uuid4(),
                org_id=org.id,
                destination_id=destination.id,
                title="Eiffel Tower Opening Hours",
                kind="attraction",
                raw_source_ref="https://www.toureiffel.paris/en/rates-opening-times",
                created_at=datetime.now(timezone.utc),
            )
            session.add(ki1)

            ki2 = KnowledgeItem(
                id=uuid4(),
                org_id=org.id,
                destination_id=destination.id,
                title="Louvre Museum Visitor Guide",
                kind="attraction",
                raw_source_ref="https://www.louvre.fr/en/visit",
                created_at=datetime.now(timezone.utc),
            )
            session.add(ki2)
            session.flush()
            print("✓ Created 2 knowledge items")

        session.commit()
        print("\n✅ Database seeded successfully!")
        print(f"   Org ID: {org.id}")
        print(f"   User ID: {user.id}")
        print(f"   Destination ID: {destination.id}")


if __name__ == "__main__":
    seed_database()
