"""Pytest configuration and fixtures for testing."""

import os
import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.config import get_settings


# Test database URL - use Postgres for integration tests
# Default to current user with no password for local development
import getpass
current_user = getpass.getuser()
TEST_POSTGRES_URL = os.environ.get(
    "TEST_POSTGRES_URL",
    f"postgresql://{current_user}@localhost:5432/keyveve_test"
)


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine with PostgreSQL."""
    # Use real Postgres for integration tests to support JSONB and other features
    engine = create_engine(
        TEST_POSTGRES_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup - drop all tables
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_db_engine):
    """Create a test database session."""
    SessionFactory = sessionmaker(bind=test_db_engine)
    session = SessionFactory()

    yield session

    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_org(test_session: Session):
    """Create a test organization."""
    from backend.app.db.models.org import Org

    org = Org(
        org_id=uuid4(),
        name="Test Organization",
        created_at=datetime.now(timezone.utc),
    )
    test_session.add(org)
    test_session.commit()
    test_session.refresh(org)

    return org


@pytest.fixture(scope="function")
def test_user(test_session: Session, test_org):
    """Create a test user."""
    from backend.app.db.models.user import User
    from backend.app.security.passwords import hash_password

    user = User(
        user_id=uuid4(),
        org_id=test_org.org_id,
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        created_at=datetime.now(timezone.utc),
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    return user


@pytest.fixture
def test_jwt_token(test_user, test_session):
    """Generate a valid JWT token for testing."""
    from backend.app.security.jwt import create_access_token
    
    # Ensure user is committed to DB
    test_session.commit()
    
    return create_access_token(test_user.user_id, test_user.org_id)


@pytest.fixture
def auth_headers(test_jwt_token, test_session):
    """Authentication headers with valid JWT token."""
    return {"Authorization": f"Bearer {test_jwt_token}"}
