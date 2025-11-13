"""Integration tests for idempotency store.

These tests verify:
1. First save_result creates entry
2. Second save_result with same key returns cached entry
3. TTL is respected (expired entries treated as missing)
4. mark_completed updates status correctly
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.idempotency.store import (
    get_entry,
    mark_completed,
    mark_error,
    save_result,
)


class TestIdempotencyStore:
    """Test idempotency store functionality."""

    def test_save_result_creates_entry(
        self, test_session: Session, test_org, test_user
    ):
        """Test that save_result creates a new entry."""
        key = "test-key-123"
        entry = save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="pending",
            body_hash="body-hash-abc",
            headers_hash="headers-hash-def",
            ttl_seconds=3600,
        )

        assert entry.key == key
        assert entry.user_id == test_user.user_id
        assert entry.org_id == test_org.org_id
        assert entry.status == "pending"
        assert entry.body_hash == "body-hash-abc"
        assert entry.headers_hash == "headers-hash-def"

    def test_get_entry_returns_valid_entry(
        self, test_session: Session, test_org, test_user
    ):
        """Test that get_entry returns entry that hasn't expired."""
        key = "test-key-456"
        save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="completed",
            body_hash="body-hash",
            headers_hash="headers-hash",
            ttl_seconds=3600,
        )
        test_session.commit()

        # Retrieve entry
        entry = get_entry(test_session, key)

        assert entry is not None
        assert entry.key == key
        assert entry.status == "completed"

    def test_get_entry_returns_none_for_expired(
        self, test_session: Session, test_org, test_user
    ):
        """Test that get_entry returns None for expired entries."""
        from backend.app.db.models.idempotency import IdempotencyEntry

        key = "expired-key"

        # Create entry that expired 1 hour ago
        expired_entry = IdempotencyEntry(
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            ttl_until=datetime.now(datetime.UTC) - timedelta(hours=1),
            status="completed",
            body_hash="body-hash",
            headers_hash="headers-hash",
            created_at=datetime.now(datetime.UTC) - timedelta(hours=25),
        )
        test_session.add(expired_entry)
        test_session.commit()

        # Try to retrieve
        entry = get_entry(test_session, key)

        # Should return None (expired)
        assert entry is None

    def test_save_result_updates_existing_entry(
        self, test_session: Session, test_org, test_user
    ):
        """Test that save_result updates existing entry instead of creating duplicate."""
        key = "update-key"

        # Create initial entry
        entry1 = save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="pending",
            body_hash="initial-hash",
            headers_hash="initial-headers",
        )
        test_session.commit()

        # Update with new status
        entry2 = save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="completed",
            body_hash="updated-hash",
            headers_hash="updated-headers",
        )
        test_session.commit()

        # Should be same entry (updated)
        assert entry2.key == entry1.key
        assert entry2.status == "completed"
        assert entry2.body_hash == "updated-hash"

        # Verify only one entry exists
        from backend.app.db.models.idempotency import IdempotencyEntry

        count = test_session.query(IdempotencyEntry).filter_by(key=key).count()
        assert count == 1

    def test_mark_completed(self, test_session: Session, test_org, test_user):
        """Test mark_completed helper."""
        key = "complete-key"

        # Create pending entry
        save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="pending",
            body_hash="pending-hash",
            headers_hash="pending-headers",
        )
        test_session.commit()

        # Mark as completed
        entry = mark_completed(
            test_session,
            key=key,
            body_hash="response-hash",
            headers_hash="response-headers",
        )
        test_session.commit()

        assert entry is not None
        assert entry.status == "completed"
        assert entry.body_hash == "response-hash"
        assert entry.headers_hash == "response-headers"

    def test_mark_error(self, test_session: Session, test_org, test_user):
        """Test mark_error helper."""
        key = "error-key"

        # Create pending entry
        save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="pending",
            body_hash="pending-hash",
            headers_hash="pending-headers",
        )
        test_session.commit()

        # Mark as error
        entry = mark_error(test_session, key)
        test_session.commit()

        assert entry is not None
        assert entry.status == "error"

    def test_idempotency_replay_scenario(
        self, test_session: Session, test_org, test_user
    ):
        """
        Test the full idempotency scenario:
        1. First request creates pending entry
        2. Request completes, marks entry as completed
        3. Second identical request retrieves cached result
        """
        key = "replay-key"

        # First request - create pending
        entry1 = save_result(
            test_session,
            key=key,
            user_id=test_user.user_id,
            org_id=test_org.org_id,
            status="pending",
            body_hash="request-hash",
            headers_hash="request-headers",
        )
        test_session.commit()
        assert entry1.status == "pending"

        # Request completes
        mark_completed(
            test_session,
            key=key,
            body_hash="response-hash",
            headers_hash="response-headers",
        )
        test_session.commit()

        # Second request - check for existing entry
        existing = get_entry(test_session, key)
        assert existing is not None
        assert existing.status == "completed"
        assert existing.body_hash == "response-hash"

        # No new entry created - service returns cached response
        from backend.app.db.models.idempotency import IdempotencyEntry

        count = test_session.query(IdempotencyEntry).filter_by(key=key).count()
        assert count == 1

    def test_get_entry_missing_key(self, test_session: Session):
        """Test get_entry returns None for non-existent key."""
        entry = get_entry(test_session, "nonexistent-key")
        assert entry is None

    def test_mark_completed_missing_key(self, test_session: Session):
        """Test mark_completed returns None for non-existent key."""
        entry = mark_completed(
            test_session,
            key="nonexistent",
            body_hash="hash",
            headers_hash="headers",
        )
        assert entry is None
