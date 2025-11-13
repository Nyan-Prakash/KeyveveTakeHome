"""Tests for idempotency schema."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.config import get_settings
from backend.app.db.base import get_engine, get_session, get_session_factory
from backend.app.db.models import IdempotencyKey


@pytest.mark.integration
class TestIdempotencySchema:
    """Tests for idempotency key schema."""

    @pytest.fixture(scope="function")
    def session_factory(self):
        """Create a session factory for tests."""
        settings = get_settings()
        engine = get_engine(settings)
        return get_session_factory(engine)

    def test_insert_idempotency_key_success(self, session_factory):
        """Test that inserting an idempotency key succeeds."""
        with get_session(session_factory) as session:
            user_id = uuid4()
            key = f"test_key_{uuid4()}"

            idem_key = IdempotencyKey(
                id=uuid4(),
                user_id=user_id,
                key=key,
                ttl_until=datetime.now(timezone.utc) + timedelta(hours=1),
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            session.add(idem_key)
            session.commit()

            # Verify it was inserted
            assert idem_key.id is not None

    def test_duplicate_user_key_raises_integrity_error(self, session_factory):
        """Test that duplicate (user_id, key) raises IntegrityError."""
        user_id = uuid4()
        key = f"test_key_{uuid4()}"

        # Insert first key
        with get_session(session_factory) as session:
            idem_key1 = IdempotencyKey(
                id=uuid4(),
                user_id=user_id,
                key=key,
                ttl_until=datetime.now(timezone.utc) + timedelta(hours=1),
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            session.add(idem_key1)
            session.commit()

        # Attempt to insert duplicate should fail
        with pytest.raises(IntegrityError):
            with get_session(session_factory) as session:
                idem_key2 = IdempotencyKey(
                    id=uuid4(),
                    user_id=user_id,  # Same user_id
                    key=key,  # Same key
                    ttl_until=datetime.now(timezone.utc) + timedelta(hours=1),
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(idem_key2)
                session.commit()

    def test_cleanup_expired_keys(self, session_factory):
        """Test querying and deleting expired idempotency keys."""
        now = datetime.now(timezone.utc)

        # Insert some expired and non-expired keys
        with get_session(session_factory) as session:
            # Expired key
            expired_key = IdempotencyKey(
                id=uuid4(),
                user_id=uuid4(),
                key=f"expired_key_{uuid4()}",
                ttl_until=now - timedelta(hours=1),  # Expired 1 hour ago
                status="completed",
                created_at=now - timedelta(hours=2),
            )
            session.add(expired_key)

            # Non-expired key
            active_key = IdempotencyKey(
                id=uuid4(),
                user_id=uuid4(),
                key=f"active_key_{uuid4()}",
                ttl_until=now + timedelta(hours=1),  # Expires in 1 hour
                status="pending",
                created_at=now,
            )
            session.add(active_key)
            session.commit()

        # Query for expired keys
        with get_session(session_factory) as session:
            expired_keys = (
                session.query(IdempotencyKey)
                .filter(IdempotencyKey.ttl_until < now)
                .all()
            )

            # At least one expired key should be found
            assert len(expired_keys) >= 1

            # Delete expired keys
            for key in expired_keys:
                session.delete(key)
            session.commit()

        # Verify expired keys are deleted
        with get_session(session_factory) as session:
            remaining_expired = (
                session.query(IdempotencyKey)
                .filter(IdempotencyKey.ttl_until < now)
                .count()
            )
            # Should be 0 (all expired keys from this test deleted)
            # Note: Other tests might have inserted expired keys, so we can't assert == 0
            # But we can verify the deletion worked by checking the specific ID
            deleted_key = session.get(IdempotencyKey, expired_key.id)
            assert deleted_key is None

    def test_different_users_same_key_allowed(self, session_factory):
        """Test that different users can use the same key."""
        key = f"shared_key_{uuid4()}"

        # Insert key for user 1
        with get_session(session_factory) as session:
            idem_key1 = IdempotencyKey(
                id=uuid4(),
                user_id=uuid4(),
                key=key,
                ttl_until=datetime.now(timezone.utc) + timedelta(hours=1),
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            session.add(idem_key1)
            session.commit()

        # Insert same key for user 2 should succeed
        with get_session(session_factory) as session:
            idem_key2 = IdempotencyKey(
                id=uuid4(),
                user_id=uuid4(),  # Different user
                key=key,  # Same key
                ttl_until=datetime.now(timezone.utc) + timedelta(hours=1),
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            session.add(idem_key2)
            session.commit()

            # Should succeed without error
            assert idem_key2.id is not None
