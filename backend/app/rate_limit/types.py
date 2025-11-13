"""Rate limiting types."""

from datetime import datetime

from pydantic import BaseModel, Field


class RateLimitResult(BaseModel):
    """Result of a rate limit check."""

    allowed: bool = Field(description="Whether the request is allowed")
    remaining: int = Field(description="Number of requests remaining in window")
    reset_at: datetime = Field(description="When the rate limit window resets")
