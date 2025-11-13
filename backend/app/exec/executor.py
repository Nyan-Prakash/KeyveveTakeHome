"""Tool executor with timeout, retry, circuit breaker, and cache support."""

import hashlib
import json
import random
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.types import (
    ExecutorErrorKind,
    ToolName,
    ToolRequest,
    ToolResponse,
)
from backend.app.metrics.core import record_tool_call


class SimpleCache(Protocol):
    """Simple cache interface for tool results."""

    def get(self, key: str) -> dict[str, Any] | None:
        """Get value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        ...

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        """Set value in cache with TTL.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        ...


class InMemoryCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self) -> None:
        """Initialize cache."""
        self._store: dict[str, tuple[dict[str, Any], datetime]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._store:
                return None
            value, expires_at = self._store[key]
            if datetime.now(UTC) > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
            self._store[key] = (value, expires_at)


class ToolRegistry(Protocol):
    """Protocol for tool registry."""

    def get_tool(self, name: ToolName) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Get tool function by name.

        Args:
            name: Tool name.

        Returns:
            Tool function that takes args dict and returns result dict.
        """
        ...


class CircuitBreaker:
    """Circuit breaker for a single tool."""

    def __init__(
        self,
        failure_threshold: int,
        timeout_seconds: int,
        half_open_timeout_seconds: int = 30,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening.
            timeout_seconds: Window size for counting failures.
            half_open_timeout_seconds: Time before allowing probe in half-open state.
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_timeout_seconds = half_open_timeout_seconds
        self.failures: deque[datetime] = deque()
        self.state: str = "closed"  # closed, open, half_open
        self.opened_at: datetime | None = None
        self.lock = threading.Lock()

    def _clean_old_failures(self) -> None:
        """Remove failures outside the timeout window."""
        cutoff = datetime.now(UTC) - timedelta(seconds=self.timeout_seconds)
        while self.failures and self.failures[0] < cutoff:
            self.failures.popleft()

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        with self.lock:
            if self.state == "closed":
                return False

            if self.state == "open":
                # Check if we should transition to half-open
                if self.opened_at and datetime.now(UTC) - self.opened_at >= timedelta(
                    seconds=self.half_open_timeout_seconds
                ):
                    self.state = "half_open"
                    return False
                return True

            # half_open state: allow probe
            return False

    def record_failure(self) -> None:
        """Record a failure."""
        with self.lock:
            self.failures.append(datetime.now(UTC))
            self._clean_old_failures()

            if self.state == "half_open":
                # Failed probe, go back to open
                self.state = "open"
                self.opened_at = datetime.now(UTC)
            elif (
                self.state == "closed" and len(self.failures) >= self.failure_threshold
            ):
                # Too many failures, open the breaker
                self.state = "open"
                self.opened_at = datetime.now(UTC)

    def record_success(self) -> None:
        """Record a success."""
        with self.lock:
            if self.state == "half_open":
                # Successful probe, close the breaker
                self.state = "closed"
                self.failures.clear()
                self.opened_at = None


class ToolExecutor:
    """Tool executor with timeout, retry, circuit breaker, and cache."""

    def __init__(
        self,
        registry: ToolRegistry,
        settings: Settings,
        cache: SimpleCache | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """Initialize tool executor.

        Args:
            registry: Tool registry.
            settings: Application settings.
            cache: Optional cache for tool results.
            rng: Optional random number generator for jitter (for testing).
        """
        self.registry = registry
        self.settings = settings
        self.cache = cache
        self.rng = rng or random.Random()
        self.breakers: dict[ToolName, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=settings.breaker_failure_threshold,
                timeout_seconds=settings.breaker_timeout_s,
            )
        )
        self.executor = ThreadPoolExecutor(max_workers=10)

    def _compute_cache_key(self, request: ToolRequest) -> str:
        """Compute deterministic cache key for request.

        Args:
            request: Tool request.

        Returns:
            SHA256 hex digest of sorted JSON.
        """
        cache_obj = {"name": request.name, "args": request.args}
        # Sort keys for deterministic JSON
        sorted_json = json.dumps(cache_obj, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(sorted_json.encode("utf-8")).hexdigest()

    def _call_tool_with_timeout(
        self,
        tool_func: Callable[[dict[str, Any]], dict[str, Any]],
        args: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Call tool with timeout.

        Args:
            tool_func: Tool function to call.
            args: Arguments to pass to tool.
            timeout_seconds: Timeout in seconds.

        Returns:
            Tuple of (result, error). One will be None.
        """
        future = self.executor.submit(tool_func, args)
        try:
            result = future.result(timeout=timeout_seconds)
            return result, None
        except FuturesTimeoutError:
            future.cancel()
            return None, "timeout"
        except Exception as e:
            return None, str(e)

    def execute(self, request: ToolRequest, ctx: RunContext) -> ToolResponse:
        """Execute tool request with all policies applied.

        Args:
            request: Tool request.
            ctx: Run context for cancellation support.

        Returns:
            Tool response.
        """
        start_time = time.time()
        retries = 0
        error_kind: ExecutorErrorKind | None = None

        # Check cancellation before starting
        if ctx.cancelled.is_set():
            latency_ms = int((time.time() - start_time) * 1000)
            response = ToolResponse(
                ok=False,
                data=None,
                error="cancelled",
                from_cache=False,
                latency_ms=latency_ms,
                retries=0,
                breaker_open=False,
            )
            record_tool_call(
                tool=request.name,
                latency_ms=latency_ms,
                ok=False,
                from_cache=False,
                retries=0,
                error_kind=None,  # Cancellation is not an error kind
            )
            return response

        # Check circuit breaker
        breaker = self.breakers[request.name]
        if breaker.is_open():
            latency_ms = int((time.time() - start_time) * 1000)
            response = ToolResponse(
                ok=False,
                data=None,
                error="circuit_open",
                from_cache=False,
                latency_ms=latency_ms,
                retries=0,
                breaker_open=True,
            )
            record_tool_call(
                tool=request.name,
                latency_ms=latency_ms,
                ok=False,
                from_cache=False,
                retries=0,
                error_kind="breaker_open",
            )
            return response

        # Check cache
        if self.cache:
            cache_key = self._compute_cache_key(request)
            cached = self.cache.get(cache_key)
            if cached is not None:
                latency_ms = int((time.time() - start_time) * 1000)
                response = ToolResponse(
                    ok=True,
                    data=cached,
                    error=None,
                    from_cache=True,
                    latency_ms=latency_ms,
                    retries=0,
                    breaker_open=False,
                )
                record_tool_call(
                    tool=request.name,
                    latency_ms=latency_ms,
                    ok=True,
                    from_cache=True,
                    retries=0,
                    error_kind=None,
                )
                return response

        # Get tool function
        tool_func = self.registry.get_tool(request.name)

        # Get timeouts
        soft_timeout_s = (
            request.timeout_soft_ms / 1000.0
            if request.timeout_soft_ms
            else self.settings.soft_timeout_s
        )
        hard_timeout_s = (
            request.timeout_hard_ms / 1000.0
            if request.timeout_hard_ms
            else self.settings.hard_timeout_s
        )

        # Attempt execution with retry
        result_data: dict[str, Any] | None = None
        error_msg: str | None = None

        for attempt in range(2):  # Initial + 1 retry = 2 total
            # Check if we have time left
            elapsed = time.time() - start_time
            if elapsed >= hard_timeout_s:
                error_msg = "hard_timeout"
                error_kind = "timeout_hard"
                break

            # Check cancellation before retry
            if attempt > 0 and ctx.cancelled.is_set():
                error_msg = "cancelled"
                error_kind = None
                break

            # Add jitter before retry
            if attempt > 0:
                jitter_ms = self.rng.randint(
                    self.settings.retry_jitter_min_ms,
                    self.settings.retry_jitter_max_ms,
                )
                time.sleep(jitter_ms / 1000.0)

            # Call tool with soft timeout
            remaining_time = hard_timeout_s - (time.time() - start_time)
            timeout = min(soft_timeout_s, remaining_time)

            result_data, error_msg = self._call_tool_with_timeout(
                tool_func, request.args, timeout
            )

            if result_data is not None:
                # Success
                breaker.record_success()
                retries = attempt
                error_kind = None
                break

            # Failure
            retries = attempt
            if error_msg == "timeout":
                # Determine if soft or hard timeout
                elapsed = time.time() - start_time
                if elapsed >= hard_timeout_s:
                    error_kind = "timeout_hard"
                else:
                    error_kind = "timeout_soft"
            else:
                error_kind = "tool_error"

        # Record failure if no success
        if result_data is None:
            breaker.record_failure()

        # Calculate final latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Build response
        ok = result_data is not None
        response = ToolResponse(
            ok=ok,
            data=result_data,
            error=error_msg if error_msg and not ok else None,
            from_cache=False,
            latency_ms=latency_ms,
            retries=retries,
            breaker_open=False,
        )

        # Cache successful responses
        if ok and self.cache and result_data is not None:
            cache_key = self._compute_cache_key(request)
            # Use weather TTL for now; can be made tool-specific later
            ttl_seconds = self.settings.weather_ttl_hours * 3600
            self.cache.set(cache_key, result_data, ttl_seconds)

        # Record metrics
        record_tool_call(
            tool=request.name,
            latency_ms=latency_ms,
            ok=ok,
            from_cache=False,
            retries=retries,
            error_kind=error_kind,
        )

        return response
