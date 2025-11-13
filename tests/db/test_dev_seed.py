"""Tests for development seed script."""

import pytest
from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.base import get_engine, get_session, get_session_factory
from backend.app.db.models import Destination, KnowledgeItem, Org, User
from scripts.dev_seed import seed_database


@pytest.mark.integration
class TestDevSeed:
    """Tests for development database seeding."""

    @pytest.fixture(scope="function")
    def session_factory(self):
        """Create a session factory for tests."""
        settings = get_settings()
        engine = get_engine(settings)
        return get_session_factory(engine)

    def test_seed_creates_required_data(self, session_factory):
        """Test that seed creates 1 org, 1 user, 1 destination."""
        # Run seed
        seed_database()

        with get_session(session_factory) as session:
            # Check org
            org_stmt = select(Org).where(Org.name == "Demo Org")
            org = session.execute(org_stmt).scalar_one_or_none()
            assert org is not None, "Demo Org not created"

            # Check user
            user_stmt = select(User).where(
                User.org_id == org.id, User.email == "demo@keyveve.com"
            )
            user = session.execute(user_stmt).scalar_one_or_none()
            assert user is not None, "Demo user not created"

            # Check destination
            dest_stmt = select(Destination).where(
                Destination.org_id == org.id, Destination.slug == "paris"
            )
            destination = session.execute(dest_stmt).scalar_one_or_none()
            assert destination is not None, "Paris destination not created"

            # Check knowledge items
            ki_stmt = select(KnowledgeItem).where(
                KnowledgeItem.org_id == org.id,
                KnowledgeItem.destination_id == destination.id,
            )
            items = session.execute(ki_stmt).scalars().all()
            assert len(items) >= 2, "Knowledge items not created"

    def test_seed_is_idempotent(self, session_factory):
        """Test that running seed multiple times doesn't create duplicates."""
        # Run seed first time
        seed_database()

        with get_session(session_factory) as session:
            # Count initial records
            org_count_1 = session.query(Org).filter(Org.name == "Demo Org").count()
            user_count_1 = (
                session.query(User).filter(User.email == "demo@keyveve.com").count()
            )

        # Run seed second time
        seed_database()

        with get_session(session_factory) as session:
            # Count records after second run
            org_count_2 = session.query(Org).filter(Org.name == "Demo Org").count()
            user_count_2 = (
                session.query(User).filter(User.email == "demo@keyveve.com").count()
            )

            # Counts should remain the same
            assert org_count_1 == org_count_2, "Seed created duplicate orgs"
            assert user_count_1 == user_count_2, "Seed created duplicate users"

            # Should still have exactly 1 of each
            assert org_count_2 == 1, "Should have exactly 1 Demo Org"
            assert user_count_2 == 1, "Should have exactly 1 demo user"
