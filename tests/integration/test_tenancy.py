"""Integration tests for tenancy enforcement.

These tests verify that:
1. Scoped queries only return data for the specified org
2. Cross-org reads yield 0 results
3. Tenancy helpers work correctly with all models
"""

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.models.destination import Destination
from backend.app.db.models.itinerary import Itinerary
from backend.app.db.models.org import Org
from backend.app.db.models.user import User
from backend.app.db.tenancy import (
    TenantRepository,
    scoped_count,
    scoped_get,
    scoped_list,
    scoped_query,
)


class TestTenancyEnforcement:
    """Test tenancy enforcement helpers."""

    def test_scoped_query_returns_only_org_data(
        self, test_session: Session, test_org: Org
    ):
        """Test that scoped_query only returns data for specified org."""
        # Create second org
        org_b = Org(
            org_id=uuid4(),
            name="Org B",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(org_b)

        # Create users in both orgs
        user_a = User(
            user_id=uuid4(),
            org_id=test_org.org_id,
            email="user_a@example.com",
            password_hash="hash",
            created_at=datetime.now(datetime.UTC),
        )
        user_b = User(
            user_id=uuid4(),
            org_id=org_b.org_id,
            email="user_b@example.com",
            password_hash="hash",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add_all([user_a, user_b])
        test_session.commit()

        # Query for org A's users
        stmt = scoped_query(test_session, User, test_org.org_id)
        results = test_session.execute(stmt).scalars().all()

        # Should only return org A's user
        assert len(results) == 1
        assert results[0].email == "user_a@example.com"
        assert results[0].org_id == test_org.org_id

    def test_scoped_query_with_filters(self, test_session: Session, test_org: Org):
        """Test scoped_query with additional filters."""
        # Create multiple destinations
        dest_paris = Destination(
            dest_id=uuid4(),
            org_id=test_org.org_id,
            city="Paris",
            country="France",
            geo={"lat": 48.8566, "lon": 2.3522},
            created_at=datetime.now(datetime.UTC),
        )
        dest_london = Destination(
            dest_id=uuid4(),
            org_id=test_org.org_id,
            city="London",
            country="UK",
            geo={"lat": 51.5074, "lon": -0.1278},
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add_all([dest_paris, dest_london])
        test_session.commit()

        # Query with additional filter
        stmt = scoped_query(test_session, Destination, test_org.org_id, city="Paris")
        results = test_session.execute(stmt).scalars().all()

        assert len(results) == 1
        assert results[0].city == "Paris"

    def test_scoped_get(self, test_session: Session, test_org: Org):
        """Test scoped_get returns single record."""
        dest = Destination(
            dest_id=uuid4(),
            org_id=test_org.org_id,
            city="Paris",
            country="France",
            geo={"lat": 48.8566, "lon": 2.3522},
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(dest)
        test_session.commit()

        # Get by dest_id
        result = scoped_get(
            test_session, Destination, test_org.org_id, dest_id=dest.dest_id
        )

        assert result is not None
        assert result.dest_id == dest.dest_id

    def test_scoped_get_wrong_org_returns_none(
        self, test_session: Session, test_org: Org
    ):
        """Test that scoped_get returns None for wrong org."""
        # Create second org
        org_b = Org(
            org_id=uuid4(),
            name="Org B",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(org_b)

        # Create dest in org B
        dest_b = Destination(
            dest_id=uuid4(),
            org_id=org_b.org_id,
            city="Paris",
            country="France",
            geo={"lat": 48.8566, "lon": 2.3522},
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(dest_b)
        test_session.commit()

        # Try to get org B's dest using org A's scope
        result = scoped_get(
            test_session, Destination, test_org.org_id, dest_id=dest_b.dest_id
        )

        # Should return None (cross-org access blocked)
        assert result is None

    def test_scoped_list(self, test_session: Session, test_org: Org):
        """Test scoped_list with limit and offset."""
        # Create multiple destinations
        for i in range(5):
            dest = Destination(
                dest_id=uuid4(),
                org_id=test_org.org_id,
                city=f"City{i}",
                country="Country",
                geo={"lat": 0.0, "lon": 0.0},
                created_at=datetime.now(datetime.UTC),
            )
            test_session.add(dest)
        test_session.commit()

        # Get first 3
        results = scoped_list(test_session, Destination, test_org.org_id, limit=3)
        assert len(results) == 3

        # Get with offset
        results = scoped_list(
            test_session, Destination, test_org.org_id, limit=2, offset=3
        )
        assert len(results) == 2

    def test_scoped_count(self, test_session: Session, test_org: Org):
        """Test scoped_count."""
        # Create destinations
        for i in range(5):
            dest = Destination(
                dest_id=uuid4(),
                org_id=test_org.org_id,
                city=f"City{i}",
                country="Country",
                geo={"lat": 0.0, "lon": 0.0},
                created_at=datetime.now(datetime.UTC),
            )
            test_session.add(dest)
        test_session.commit()

        count = scoped_count(test_session, Destination, test_org.org_id)
        assert count == 5

    def test_tenant_repository(self, test_session: Session, test_org: Org):
        """Test TenantRepository class."""
        # Create repository scoped to test_org
        repo = TenantRepository(test_session, test_org.org_id)

        # Create destinations
        dest = Destination(
            dest_id=uuid4(),
            org_id=test_org.org_id,
            city="Paris",
            country="France",
            geo={"lat": 48.8566, "lon": 2.3522},
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(dest)
        test_session.commit()

        # Use repository methods
        result = repo.get(Destination, dest_id=dest.dest_id)
        assert result is not None
        assert result.dest_id == dest.dest_id

        results = repo.list(Destination)
        assert len(results) == 1

        count = repo.count(Destination)
        assert count == 1

    def test_cross_org_audit_query(self, test_session: Session, test_org: Org):
        """
        Test the cross-org audit query from SPEC:
        SELECT COUNT(*) FROM itinerary i JOIN user u ON i.user_id = u.user_id
        WHERE i.org_id != u.org_id

        This should always return 0 (no cross-org data leakage).
        """
        # Create second org
        org_b = Org(
            org_id=uuid4(),
            name="Org B",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(org_b)

        # Create users
        user_a = User(
            user_id=uuid4(),
            org_id=test_org.org_id,
            email="user_a@example.com",
            password_hash="hash",
            created_at=datetime.now(datetime.UTC),
        )
        user_b = User(
            user_id=uuid4(),
            org_id=org_b.org_id,
            email="user_b@example.com",
            password_hash="hash",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add_all([user_a, user_b])
        test_session.commit()

        # Create itineraries (correctly scoped)
        from backend.app.db.models.agent_run import AgentRun

        run_a = AgentRun(
            run_id=uuid4(),
            org_id=test_org.org_id,
            user_id=user_a.user_id,
            intent={"city": "Paris"},
            trace_id="trace-a",
            status="completed",
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(run_a)
        test_session.commit()

        itin_a = Itinerary(
            itinerary_id=uuid4(),
            org_id=test_org.org_id,
            run_id=run_a.run_id,
            user_id=user_a.user_id,
            data={"days": []},
            created_at=datetime.now(datetime.UTC),
        )
        test_session.add(itin_a)
        test_session.commit()

        # Audit query
        from sqlalchemy import func, select

        audit_stmt = (
            select(func.count())
            .select_from(Itinerary)
            .join(User, Itinerary.user_id == User.user_id)
            .where(Itinerary.org_id != User.org_id)
        )

        mismatched_count = test_session.execute(audit_stmt).scalar()

        # Should be 0 (no cross-org leakage)
        assert mismatched_count == 0

    def test_model_without_org_id_raises_error(self, test_session: Session):
        """Test that scoped_query raises error for models without org_id."""
        from backend.app.db.models.refresh_token import RefreshToken

        with pytest.raises(AttributeError, match="does not have org_id column"):
            scoped_query(test_session, RefreshToken, uuid4())
