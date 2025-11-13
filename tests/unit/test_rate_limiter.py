"""Tests for rate limiter implementation."""

from datetime import timedelta
from time import sleep
from uuid import uuid4

import pytest

from backend.app.rate_limit.core import InMemoryRateLimiter


@pytest.mark.unit
class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    def test_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = InMemoryRateLimiter()
        user_id = uuid4()
        bucket = "test_bucket"
        limit = 3
        window = timedelta(seconds=60)

        # First 3 requests should be allowed
        for i in range(3):
            result = limiter.check_and_consume(user_id, bucket, limit, window)
            assert result.allowed is True
            assert result.remaining == 2 - i

    def test_denies_request_exceeding_limit(self):
        """Test that requests exceeding limit are denied."""
        limiter = InMemoryRateLimiter()
        user_id = uuid4()
        bucket = "test_bucket"
        limit = 3
        window = timedelta(seconds=60)

        # First 3 requests allowed
        for _ in range(3):
            result = limiter.check_and_consume(user_id, bucket, limit, window)
            assert result.allowed is True

        # 4th request should be denied
        result = limiter.check_and_consume(user_id, bucket, limit, window)
        assert result.allowed is False
        assert result.remaining == 0

    def test_window_reset_allows_new_requests(self):
        """Test that requests are allowed after window expires."""
        limiter = InMemoryRateLimiter()
        user_id = uuid4()
        bucket = "test_bucket"
        limit = 2
        window = timedelta(seconds=1)  # 1 second window

        # Use up the limit
        result1 = limiter.check_and_consume(user_id, bucket, limit, window)
        result2 = limiter.check_and_consume(user_id, bucket, limit, window)
        assert result1.allowed is True
        assert result2.allowed is True

        # 3rd request should be denied
        result3 = limiter.check_and_consume(user_id, bucket, limit, window)
        assert result3.allowed is False

        # Wait for window to expire
        sleep(1.1)

        # Should be allowed again
        result4 = limiter.check_and_consume(user_id, bucket, limit, window)
        assert result4.allowed is True
        assert result4.remaining == 1

    def test_different_users_independent_limits(self):
        """Test that different users have independent rate limits."""
        limiter = InMemoryRateLimiter()
        user1 = uuid4()
        user2 = uuid4()
        bucket = "test_bucket"
        limit = 2
        window = timedelta(seconds=60)

        # User 1 uses up their limit
        limiter.check_and_consume(user1, bucket, limit, window)
        limiter.check_and_consume(user1, bucket, limit, window)

        # User 2 should still be able to make requests
        result = limiter.check_and_consume(user2, bucket, limit, window)
        assert result.allowed is True
        assert result.remaining == 1

    def test_different_buckets_independent_limits(self):
        """Test that different buckets have independent rate limits."""
        limiter = InMemoryRateLimiter()
        user_id = uuid4()
        bucket1 = "agent_runs"
        bucket2 = "crud"
        limit = 2
        window = timedelta(seconds=60)

        # Use up limit in bucket1
        limiter.check_and_consume(user_id, bucket1, limit, window)
        limiter.check_and_consume(user_id, bucket1, limit, window)

        # bucket2 should still allow requests
        result = limiter.check_and_consume(user_id, bucket2, limit, window)
        assert result.allowed is True
        assert result.remaining == 1

    def test_hammer_test_does_not_over_allow(self):
        """Test that rapid consecutive requests don't bypass the limit."""
        limiter = InMemoryRateLimiter()
        user_id = uuid4()
        bucket = "test_bucket"
        limit = 5
        window = timedelta(seconds=60)

        allowed_count = 0
        denied_count = 0

        # Make 20 rapid requests
        for _ in range(20):
            result = limiter.check_and_consume(user_id, bucket, limit, window)
            if result.allowed:
                allowed_count += 1
            else:
                denied_count += 1

        # Exactly 5 should be allowed, 15 denied
        assert allowed_count == 5
        assert denied_count == 15
