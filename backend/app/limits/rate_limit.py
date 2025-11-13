"""Redis-based rate limiting using token bucket algorithm.

This module provides a pure API for rate limiting that does not depend on FastAPI.
It uses Redis to maintain per-user, per-bucket rate limit state.
"""

import time
from typing import Literal

import redis
from pydantic import BaseModel

from backend.app.config import get_settings

# Bucket configurations: limit per minute
BUCKET_LIMITS = {
    "agent": 5,  # 5 requests/min for agent endpoints
    "crud": 60,  # 60 requests/min for CRUD operations
}

BucketType = Literal["agent", "crud"]


class RateLimitResult(BaseModel):
    """Result of a rate limit check."""

    allowed: bool
    retry_after_seconds: int | None = None
    remaining: int | None = None


def get_redis_client() -> redis.Redis:
    """Get Redis client for rate limiting."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def check_rate_limit(
    user_id: str,
    bucket: BucketType,
    limit_per_minute: int | None = None,
) -> RateLimitResult:
    """
    Check if a request is allowed under rate limits using token bucket algorithm.

    Args:
        user_id: User ID to rate limit
        bucket: Bucket type ("agent" or "crud")
        limit_per_minute: Optional override for rate limit (default: from BUCKET_LIMITS)

    Returns:
        RateLimitResult with allowed status and retry_after if blocked

    Algorithm:
        - Uses a sliding window token bucket approach
        - Stores (tokens, last_refill_time) in Redis
        - Refills tokens based on time elapsed since last refill
        - Max tokens = limit_per_minute
        - Refill rate = limit_per_minute / 60 tokens per second

    Example:
        result = check_rate_limit("user-123", "agent")
        if not result.allowed:
            # Return 429 with Retry-After: result.retry_after_seconds
            pass
    """
    client = get_redis_client()

    # Get limit from config or override
    limit = limit_per_minute if limit_per_minute is not None else BUCKET_LIMITS[bucket]

    # Redis key for this user+bucket
    key = f"rate_limit:{user_id}:{bucket}"

    # Current time in seconds
    now = time.time()

    # Get current state from Redis
    pipe = client.pipeline()
    pipe.hget(key, "tokens")
    pipe.hget(key, "last_refill")
    tokens_str, last_refill_str = pipe.execute()

    if tokens_str is None or last_refill_str is None:
        # First request - initialize bucket
        tokens = float(limit - 1)  # Consume 1 token for this request
        last_refill = now
    else:
        tokens = float(tokens_str)
        last_refill = float(last_refill_str)

        # Calculate tokens to add based on time elapsed
        time_elapsed = now - last_refill
        refill_rate = limit / 60.0  # tokens per second
        tokens_to_add = time_elapsed * refill_rate

        # Refill tokens (capped at limit)
        tokens = min(limit, tokens + tokens_to_add)
        last_refill = now

        # Try to consume 1 token
        tokens -= 1

    # Check if we have tokens available
    if tokens >= 0:
        # Allowed - save new state
        pipe = client.pipeline()
        pipe.hset(key, "tokens", str(tokens))
        pipe.hset(key, "last_refill", str(last_refill))
        pipe.expire(key, 120)  # Expire after 2 minutes of inactivity
        pipe.execute()

        return RateLimitResult(
            allowed=True,
            retry_after_seconds=None,
            remaining=int(tokens),
        )
    else:
        # Not allowed - calculate retry_after
        # How long until we have 1 token?
        tokens_needed = abs(tokens) + 1
        refill_rate = limit / 60.0  # tokens per second
        retry_after_seconds = int(tokens_needed / refill_rate) + 1

        # Don't update state - request is rejected
        return RateLimitResult(
            allowed=False,
            retry_after_seconds=retry_after_seconds,
            remaining=0,
        )


def reset_rate_limit(user_id: str, bucket: BucketType) -> None:
    """
    Reset rate limit for a user+bucket (useful for testing).

    Args:
        user_id: User ID
        bucket: Bucket type
    """
    client = get_redis_client()
    key = f"rate_limit:{user_id}:{bucket}"
    client.delete(key)
