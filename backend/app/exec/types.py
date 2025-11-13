"""Type definitions for tool execution."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Type alias for tool callables - can be sync or async
ToolCallable = Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]


class ToolResult(BaseModel):
    """Result of a tool execution."""

    status: Literal["success", "error", "timeout", "cancelled", "breaker_open"]
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    from_cache: bool = False
    latency_ms: int
    retries: int = 0


class CachePolicy(BaseModel):
    """Policy for caching tool results."""

    enabled: bool = False
    ttl_seconds: int = Field(default=3600, description="Time-to-live in seconds")


class BreakerPolicy(BaseModel):
    """Policy for circuit breaker behavior."""

    failure_threshold: int = Field(
        default=5, description="Number of failures before opening breaker"
    )
    window_seconds: int = Field(
        default=60, description="Time window for counting failures"
    )
    cooldown_seconds: int = Field(
        default=30, description="Cooldown before allowing probe in half-open state"
    )


class CircuitBreakerState(BaseModel):
    """State of a circuit breaker."""

    failures: int = 0
    opened_at: datetime | None = None
    state: Literal["closed", "open", "half_open"] = "closed"


class CancelToken:
    """Simple cancellation token."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Mark this token as cancelled."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if this token has been cancelled."""
        return self._cancelled
