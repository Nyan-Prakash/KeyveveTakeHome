"""Rate limiting package."""

from .rate_limit import RateLimitResult, check_rate_limit

__all__ = ["RateLimitResult", "check_rate_limit"]
