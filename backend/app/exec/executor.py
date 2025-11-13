"""Tool executor with timeouts, retries, circuit breaking, and caching."""

import asyncio
import hashlib
import inspect
import json
import time
from datetime import UTC, datetime
from typing import Any, Protocol

from backend.app.config import Settings, get_settings
from backend.app.exec.types import (
    BreakerPolicy,
    CachePolicy,
    CancelToken,
    CircuitBreakerState,
    ToolCallable,
    ToolResult,
)


class Clock(Protocol):
    """Protocol for time operations (allows testing)."""

    def now(self) -> datetime:
        """Get current time."""
        ...

    def time(self) -> float:
        """Get current time as timestamp."""
        ...

    def sleep(self, seconds: float) -> None:
        """Sleep for given seconds."""
        ...


class SystemClock:
    """Real system clock implementation."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ToolCache(Protocol):
    """Protocol for tool result caching."""

    def get(self, key: str) -> ToolResult | None:
        """Get cached result by key."""
        ...

    def set(self, key: str, value: ToolResult, ttl_seconds: int) -> None:
        """Set cached result with TTL."""
        ...


class InMemoryToolCache:
    """Simple in-memory cache implementation with expiry."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[ToolResult, float]] = {}

    def get(self, key: str) -> ToolResult | None:
        """Get cached result if not expired."""
        if key not in self._cache:
            return None

        result, expires_at = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None

        return result

    def set(self, key: str, value: ToolResult, ttl_seconds: int) -> None:
        """Set cached result with expiry time."""
        expires_at = time.time() + ttl_seconds
        self._cache[key] = (value, expires_at)


class ToolExecutor:
    """
    Executor for tool calls with comprehensive resilience patterns.

    Handles:
    - Caching with content-based keys
    - Soft/hard timeouts
    - Retries with jitter
    - Circuit breaking per tool
    - Cancellation tokens
    - Metrics emission
    """

    def __init__(
        self,
        metrics: Any,  # MetricsClient type
        cache: ToolCache | None = None,
        clock: Clock | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._metrics = metrics
        self._cache = cache or InMemoryToolCache()
        self._clock = clock or SystemClock()
        self._settings = settings or get_settings()

        # Circuit breaker state per tool
        self._breakers: dict[str, CircuitBreakerState] = {}

    def execute(
        self,
        tool: ToolCallable,
        name: str,
        args: dict[str, Any],
        *,
        cache_policy: CachePolicy,
        breaker_policy: BreakerPolicy,
        cancel_token: CancelToken | None = None,
    ) -> ToolResult:
        """
        Execute a tool with full resilience patterns.

        Args:
            tool: The callable to execute
            name: Tool name for metrics/logging
            args: Arguments to pass to tool
            cache_policy: Caching configuration
            breaker_policy: Circuit breaker configuration
            cancel_token: Optional cancellation token

        Returns:
            ToolResult with status, data/error, and metadata
        """
        start_time = self._clock.time()

        # Check cancellation before starting
        if cancel_token and cancel_token.is_cancelled():
            result = ToolResult(
                status="cancelled",
                error={"reason": "cancelled"},
                latency_ms=0,
                retries=0,
            )
            self._metrics.inc_tool_errors(name, "cancelled")
            self._metrics.observe_tool_latency(name, "cancelled", 0)
            return result

        # Check cache
        cache_key = self._compute_cache_key(name, args)
        if cache_policy.enabled:
            cached = self._cache.get(cache_key)
            if cached is not None:
                # Cache hit - update metrics and return
                self._metrics.inc_tool_cache_hit(name)
                self._metrics.observe_tool_latency(
                    name, cached.status, cached.latency_ms
                )
                # Return cached result with from_cache flag
                cached_copy = cached.model_copy()
                cached_copy.from_cache = True
                return cached_copy

        # Check circuit breaker
        breaker_state = self._get_breaker_state(name, breaker_policy)
        if breaker_state.state == "open":
            # Check if cooldown has elapsed
            assert breaker_state.opened_at is not None
            time_since_open = (
                self._clock.now() - breaker_state.opened_at
            ).total_seconds()

            if time_since_open < breaker_policy.cooldown_seconds:
                # Still in cooldown - reject immediately
                retry_after = int(breaker_policy.cooldown_seconds - time_since_open)
                result = ToolResult(
                    status="error",
                    error={
                        "reason": "breaker_open",
                        "retry_after_seconds": retry_after,
                    },
                    latency_ms=int((self._clock.time() - start_time) * 1000),
                    retries=0,
                )
                self._metrics.inc_tool_errors(name, "breaker_open")
                self._metrics.observe_tool_latency(name, "error", result.latency_ms)
                return result
            else:
                # Cooldown elapsed - transition to half-open for probe
                breaker_state.state = "half_open"
                self._metrics.set_breaker_state(name, "half_open")

        # Execute with retries
        result = self._execute_with_retries(
            tool,
            name,
            args,
            cancel_token,
            breaker_policy,
        )

        # Update circuit breaker based on result
        self._update_breaker(name, result, breaker_policy)

        # Cache successful results
        if (
            cache_policy.enabled
            and result.status == "success"
            and not result.from_cache
        ):
            self._cache.set(cache_key, result, cache_policy.ttl_seconds)

        # Emit metrics
        self._metrics.observe_tool_latency(name, result.status, result.latency_ms)
        if result.retries > 0:
            self._metrics.inc_tool_retries(name, result.retries)
        # Only record final error if status is not success
        # (intermediate retry errors are already recorded in _execute_with_retries)
        if result.status != "success":
            # Check if this error was already recorded during retry
            # We only want to record if retries == 0 (no retry) or if it's final failure
            if result.retries == 0:
                error_reason = "unknown"
                if result.error:
                    error_reason = result.error.get("reason", "unknown")
                self._metrics.inc_tool_errors(name, error_reason)

        return result

    def _execute_with_retries(
        self,
        tool: ToolCallable,
        name: str,
        args: dict[str, Any],
        cancel_token: CancelToken | None,
        breaker_policy: BreakerPolicy,
    ) -> ToolResult:
        """Execute tool with retry logic."""
        max_retries = 1
        retries = 0
        start_time = self._clock.time()

        for attempt in range(max_retries + 1):
            # Check cancellation before each attempt
            if cancel_token and cancel_token.is_cancelled():
                return ToolResult(
                    status="cancelled",
                    error={"reason": "cancelled"},
                    latency_ms=int((self._clock.time() - start_time) * 1000),
                    retries=retries,
                )

            result = self._execute_once(tool, name, args)

            # Success - return immediately
            if result.status == "success":
                result.retries = retries
                # Update latency to reflect total time including retries
                result.latency_ms = int((self._clock.time() - start_time) * 1000)
                return result

            # Check if we should retry
            should_retry = (
                attempt < max_retries
                and result.status in ("timeout", "error")
                and self._is_retryable_error(result)
            )

            if not should_retry:
                result.retries = retries
                # Update latency to reflect total time
                result.latency_ms = int((self._clock.time() - start_time) * 1000)
                return result

            # Record error for this attempt (before retry)
            if result.error:
                error_reason = result.error.get("reason", "unknown")
                self._metrics.inc_tool_errors(name, error_reason)

            # Increment retry counter
            retries += 1

            # Jitter backoff before retry
            jitter_ms = self._settings.retry_jitter_min_ms + (
                hash(f"{name}{attempt}")
                % (
                    self._settings.retry_jitter_max_ms
                    - self._settings.retry_jitter_min_ms
                )
            )
            backoff_seconds = jitter_ms / 1000.0

            # Sleep with cancellation check
            sleep_start = self._clock.time()
            while self._clock.time() - sleep_start < backoff_seconds:
                if cancel_token and cancel_token.is_cancelled():
                    return ToolResult(
                        status="cancelled",
                        error={"reason": "cancelled"},
                        latency_ms=int((self._clock.time() - start_time) * 1000),
                        retries=retries,
                    )
                self._clock.sleep(0.01)  # Check every 10ms

        # Should not reach here
        result.retries = retries
        result.latency_ms = int((self._clock.time() - start_time) * 1000)
        return result

    def _execute_once(
        self,
        tool: ToolCallable,
        name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute tool once with timeout."""
        start_time = self._clock.time()

        try:
            # Check if tool is async
            if inspect.iscoroutinefunction(tool):
                # Async tool
                result_data = asyncio.run(self._execute_async_with_timeout(tool, args))
            else:
                # Sync tool
                result_data = self._execute_sync_with_timeout(tool, args)

            latency_ms = int((self._clock.time() - start_time) * 1000)

            return ToolResult(
                status="success",
                data=result_data,
                latency_ms=latency_ms,
                retries=0,
            )

        except TimeoutError:
            latency_ms = int((self._clock.time() - start_time) * 1000)
            return ToolResult(
                status="timeout",
                error={"reason": "timeout"},
                latency_ms=latency_ms,
                retries=0,
            )

        except Exception as e:
            latency_ms = int((self._clock.time() - start_time) * 1000)
            return ToolResult(
                status="error",
                error={
                    "reason": "exception",
                    "type": type(e).__name__,
                    "message": str(e),
                },
                latency_ms=latency_ms,
                retries=0,
            )

    async def _execute_async_with_timeout(
        self, tool: ToolCallable, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute async tool with timeout."""
        soft_timeout = self._settings.soft_timeout_s

        try:
            # Call tool and await if it's a coroutine
            result_or_awaitable = tool(args)
            if inspect.iscoroutine(result_or_awaitable):
                result = await asyncio.wait_for(result_or_awaitable, timeout=soft_timeout)
            else:
                result = result_or_awaitable
            # Handle case where async function returns dict directly
            return result if isinstance(result, dict) else {"result": result}
        except TimeoutError:
            raise TimeoutError("Tool execution exceeded soft timeout") from None

    def _execute_sync_with_timeout(
        self, tool: ToolCallable, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute sync tool with timeout using threading."""
        import concurrent.futures

        soft_timeout = self._settings.soft_timeout_s

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool, args)
            try:
                result = future.result(timeout=soft_timeout)
                return result if isinstance(result, dict) else {"result": result}
            except concurrent.futures.TimeoutError:
                # Try to cancel the future
                future.cancel()
                raise TimeoutError("Tool execution exceeded soft timeout") from None

    def _is_retryable_error(self, result: ToolResult) -> bool:
        """Determine if an error is retryable."""
        if result.status == "timeout":
            return True

        if result.status == "error" and result.error:
            # Consider some error types retryable
            error_type = result.error.get("type", "")
            # Network errors, temporary failures, etc.
            retryable_types = {
                "ConnectionError",
                "TimeoutError",
                "TemporaryError",
            }
            return error_type in retryable_types

        return False

    def _compute_cache_key(self, name: str, args: dict[str, Any]) -> str:
        """Compute stable cache key from tool name and args."""
        # Sort keys to ensure stable ordering
        normalized = json.dumps(
            {"tool": name, "args": args}, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _get_breaker_state(
        self, name: str, policy: BreakerPolicy
    ) -> CircuitBreakerState:
        """Get or create circuit breaker state for a tool."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreakerState()
        return self._breakers[name]

    def _update_breaker(
        self, name: str, result: ToolResult, policy: BreakerPolicy
    ) -> None:
        """Update circuit breaker state based on result."""
        breaker = self._get_breaker_state(name, policy)

        if result.status == "success":
            # Success - reset breaker if in half-open or close if open
            if breaker.state in ("half_open", "open"):
                breaker.state = "closed"
                breaker.failures = 0
                breaker.opened_at = None
                self._metrics.set_breaker_state(name, "closed")
            elif breaker.state == "closed":
                # Decay failures on success
                breaker.failures = max(0, breaker.failures - 1)

        else:
            # Failure - increment counter
            breaker.failures += 1

            # Check if we should open the breaker
            if (
                breaker.state == "closed"
                and breaker.failures >= policy.failure_threshold
            ):
                breaker.state = "open"
                breaker.opened_at = self._clock.now()
                self._metrics.inc_breaker_open(name)
                self._metrics.set_breaker_state(name, "open")

            elif breaker.state == "half_open":
                # Probe failed - re-open
                breaker.state = "open"
                breaker.opened_at = self._clock.now()
                self._metrics.inc_breaker_open(name)
                self._metrics.set_breaker_state(name, "open")
