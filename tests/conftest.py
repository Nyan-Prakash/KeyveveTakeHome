"""Pytest configuration and fixtures for testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine with in-memory SQLite."""
    # Use SQLite in-memory for fast tests
    # Note: Some Postgres-specific features (like pgvector) won't work in SQLite
    # For full integration tests with Postgres, use a test database
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_db_engine):
    """Create a test database session."""
    SessionFactory = sessionmaker(bind=test_db_engine)
    session = SessionFactory()

    yield session

    session.close()


@pytest.fixture(scope="function")
def test_org(test_session: Session):
    """Create a test organization."""
    from datetime import datetime
    from uuid import uuid4

    from backend.app.db.models.org import Org

    org = Org(
        org_id=uuid4(),
        name="Test Organization",
        created_at=datetime.now(datetime.UTC),
    )
    test_session.add(org)
    test_session.commit()

    return org


@pytest.fixture(scope="function")
def test_user(test_session: Session, test_org):
    """Create a test user."""
    from datetime import datetime
    from uuid import uuid4

    from backend.app.db.models.user import User

    user = User(
        user_id=uuid4(),
        org_id=test_org.org_id,
        email="test@example.com",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$placeholder",
        created_at=datetime.now(datetime.UTC),
    )
    test_session.add(user)
    test_session.commit()

    return user
