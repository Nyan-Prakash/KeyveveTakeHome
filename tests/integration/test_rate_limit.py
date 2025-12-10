"""Integration tests for rate limiting.

These tests verify:
1. Token bucket algorithm works correctly
2. Agent bucket: 5 requests/min
3. CRUD bucket: 60 requests/min
4. Retry-after is calculated correctly when limit exceeded
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.app.limits.rate_limit import check_rate_limit, reset_rate_limit


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting functionality."""

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_first_requests_allowed(self, mock_redis_client):
        """Test that first N requests within limit are allowed."""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        # Mock initial state (no existing bucket)
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [None, None]  # tokens, last_refill
        mock_redis.pipeline.return_value = mock_pipeline

        user_id = "user-123"
        bucket = "agent"

        # First request
        result = check_rate_limit(user_id, bucket)

        assert result.allowed is True
        assert result.retry_after_seconds is None
        assert result.remaining == 4  # 5 limit - 1 consumed = 4

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_agent_bucket_limit_exceeded(self, mock_redis_client):
        """Test that agent bucket (5/min) blocks 6th request."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-456"
        bucket = "agent"

        # Simulate 5 requests consumed (0 tokens left)
        mock_pipeline = MagicMock()
        now = time.time()
        mock_pipeline.execute.return_value = [str(0.0), str(now)]  # 0 tokens left
        mock_redis.pipeline.return_value = mock_pipeline

        # 6th request should be blocked
        result = check_rate_limit(user_id, bucket)

        assert result.allowed is False
        assert result.retry_after_seconds is not None
        assert result.retry_after_seconds > 0
        assert result.remaining == 0

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_token_refill_over_time(self, mock_redis_client):
        """Test that tokens refill based on time elapsed."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-789"
        bucket = "agent"

        # Simulate: used all 5 tokens, then waited 30 seconds
        # Refill rate = 5 tokens / 60 seconds = 0.0833 tokens/second
        # After 30s: 30 * 0.0833 = 2.5 tokens added
        # New balance: 0 + 2.5 = 2.5 tokens
        # Consuming 1 leaves: 1.5 tokens

        mock_pipeline = MagicMock()
        now = time.time()
        last_refill = now - 30  # 30 seconds ago
        mock_pipeline.execute.return_value = [str(0.0), str(last_refill)]
        mock_redis.pipeline.return_value = mock_pipeline

        # Request should be allowed (we have ~2.5 tokens available)
        result = check_rate_limit(user_id, bucket)

        assert result.allowed is True
        assert (
            result.remaining >= 1
        )  # Should have at least 1 token left after consuming 1

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_crud_bucket_higher_limit(self, mock_redis_client):
        """Test that CRUD bucket has higher limit (60/min)."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-crud"
        bucket = "crud"

        # Mock initial state
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [None, None]
        mock_redis.pipeline.return_value = mock_pipeline

        # First request to CRUD bucket
        result = check_rate_limit(user_id, bucket)

        assert result.allowed is True
        assert result.remaining == 59  # 60 limit - 1 consumed

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_custom_limit_override(self, mock_redis_client):
        """Test that custom limit can be specified."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-custom"
        bucket = "agent"
        custom_limit = 10  # Override to 10/min

        # Mock initial state
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [None, None]
        mock_redis.pipeline.return_value = mock_pipeline

        # Request with custom limit
        result = check_rate_limit(user_id, bucket, limit_per_minute=custom_limit)

        assert result.allowed is True
        assert result.remaining == 9  # 10 limit - 1 consumed

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_retry_after_calculation(self, mock_redis_client):
        """Test that retry_after is calculated correctly."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-retry"
        bucket = "agent"

        # Simulate: -1 tokens (1 token in debt)
        # Need to wait until we have 1 token
        # Refill rate = 5/60 = 0.0833 tokens/sec
        # Tokens needed = 1 (to get back to 0) + 1 (for this request) = 2
        # Time = 2 / 0.0833 = ~24 seconds

        mock_pipeline = MagicMock()
        now = time.time()
        mock_pipeline.execute.return_value = [str(-1.0), str(now)]
        mock_redis.pipeline.return_value = mock_pipeline

        result = check_rate_limit(user_id, bucket)

        assert result.allowed is False
        assert result.retry_after_seconds is not None
        # Should be around 24 seconds (with some tolerance)
        assert 20 <= result.retry_after_seconds <= 30

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_different_users_independent_buckets(self, mock_redis_client):
        """Test that different users have independent rate limit buckets."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        # Mock that each user starts fresh
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [None, None]
        mock_redis.pipeline.return_value = mock_pipeline

        # User 1
        result1 = check_rate_limit("user-1", "agent")
        assert result1.allowed is True

        # User 2 (independent bucket)
        result2 = check_rate_limit("user-2", "agent")
        assert result2.allowed is True

        # Verify different Redis keys used
        calls = mock_redis.pipeline.return_value.hget.call_args_list
        # Should have calls for both user-1 and user-2 keys
        assert any("user-1" in str(call) for call in calls)
        assert any("user-2" in str(call) for call in calls)

    @patch("backend.app.limits.rate_limit.get_redis_client")
    def test_reset_rate_limit(self, mock_redis_client):
        """Test reset_rate_limit helper."""
        mock_redis = MagicMock()
        mock_redis_client.return_value = mock_redis

        user_id = "user-reset"
        bucket = "agent"

        reset_rate_limit(user_id, bucket)

        # Verify delete was called with correct key
        mock_redis.delete.assert_called_once_with(f"rate_limit:{user_id}:{bucket}")
