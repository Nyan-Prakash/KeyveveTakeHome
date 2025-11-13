"""Core rate limiting logic."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from backend.app.rate_limit.types import RateLimitResult


class RateLimiter(Protocol):
    """Protocol for rate limiting implementations."""

    def check_and_consume(
        self,
        user_id: UUID,
        bucket: str,
        limit: int,
        window: timedelta,
    ) -> RateLimitResult:
        """Check rate limit and consume a token if allowed.

        Args:
            user_id: User identifier.
            bucket: Rate limit bucket name (e.g., "agent_runs", "crud").
            limit: Maximum number of requests allowed in the window.
            window: Time window for the rate limit.

        Returns:
            RateLimitResult indicating if the request is allowed.
        """
        ...


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm.

    This implementation is suitable for development and testing.
    For production, use a distributed store like Redis.
    """

    def __init__(self) -> None:
        """Initialize the in-memory rate limiter."""
        # Structure: {(user_id, bucket): [(timestamp, expiry_time), ...]}
        self._requests: dict[tuple[UUID, str], list[tuple[datetime, datetime]]] = defaultdict(list)

    def check_and_consume(
        self,
        user_id: UUID,
        bucket: str,
        limit: int,
        window: timedelta,
    ) -> RateLimitResult:
        """Check rate limit and consume a token if allowed.

        Args:
            user_id: User identifier.
            bucket: Rate limit bucket name.
            limit: Maximum number of requests allowed in the window.
            window: Time window for the rate limit.

        Returns:
            RateLimitResult indicating if the request is allowed.
        """
        now = datetime.now(UTC)
        key = (user_id, bucket)

        # Clean up expired requests
        self._requests[key] = [
            (ts, exp) for ts, exp in self._requests[key] if exp > now
        ]

        current_count = len(self._requests[key])
        reset_at = now + window

        if current_count < limit:
            # Allow the request and record it
            self._requests[key].append((now, reset_at))
            return RateLimitResult(
                allowed=True,
                remaining=limit - current_count - 1,
                reset_at=reset_at,
            )
        else:
            # Rate limit exceeded
            # Find the earliest reset time among active requests
            if self._requests[key]:
                earliest_expiry = min(exp for _, exp in self._requests[key])
                reset_at = earliest_expiry

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
            )
