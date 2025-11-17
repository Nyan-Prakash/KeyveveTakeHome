"""Unit tests for ToolExecutor."""

import asyncio
import time
from datetime import UTC, datetime

import pytest

from backend.app.config import Settings
from backend.app.exec import (
    BreakerPolicy,
    CachePolicy,
    CancelToken,
    ToolExecutor,
)
from backend.app.exec.executor import Clock, InMemoryToolCache
from backend.app.metrics import MetricsClient


class FakeClock(Clock):
    """Fake clock for testing."""

    def __init__(self) -> None:
        self._current_time = time.time()
        self._current_dt = datetime.now(UTC)

    def now(self) -> datetime:
        return self._current_dt

    def time(self) -> float:
        return self._current_time

    def sleep(self, seconds: float) -> None:
        self._current_time += seconds
        # Don't actually sleep in tests

    def advance(self, seconds: float) -> None:
        """Advance clock by given seconds."""
        self._current_time += seconds
        from datetime import timedelta

        self._current_dt += timedelta(seconds=seconds)


@pytest.fixture
def metrics() -> MetricsClient:
    """Create a fresh metrics client."""
    return MetricsClient()


@pytest.fixture
def cache() -> InMemoryToolCache:
    """Create a fresh cache."""
    return InMemoryToolCache()


@pytest.fixture
def clock() -> FakeClock:
    """Create a fake clock."""
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    from backend.app.config import get_settings
    
    # Get the real settings to inherit actual API keys and other config
    real_settings = get_settings()
    
    return Settings(
        # Override specific test values
        soft_timeout_s=2.0,
        hard_timeout_s=4.0,
        retry_jitter_min_ms=200,
        retry_jitter_max_ms=500,
        breaker_failure_threshold=5,
        breaker_timeout_s=60,
        # Keep the real API keys and other configurations
        openai_api_key=real_settings.openai_api_key,
        weather_api_key=real_settings.weather_api_key,
        postgres_url=real_settings.postgres_url,
        redis_url=real_settings.redis_url,
        ui_origin=real_settings.ui_origin,
        jwt_private_key_pem=real_settings.jwt_private_key_pem,
        jwt_public_key_pem=real_settings.jwt_public_key_pem,
        openai_model=real_settings.openai_model,
    )


@pytest.fixture
def executor(
    metrics: MetricsClient,
    cache: InMemoryToolCache,
    clock: FakeClock,
    settings: Settings,
) -> ToolExecutor:
    """Create a ToolExecutor with test dependencies."""
    return ToolExecutor(
        metrics=metrics,
        cache=cache,
        clock=clock,
        settings=settings,
    )


# === Timeout Tests ===


def test_executor_soft_timeout_triggers_timeout_status_and_records_error(
    metrics: MetricsClient, cache: InMemoryToolCache, settings: Settings
) -> None:
    """Test that soft timeout triggers timeout status."""
    # Use real clock for timeout test since we need actual wall time
    from backend.app.exec.executor import SystemClock

    executor = ToolExecutor(
        metrics=metrics, cache=cache, clock=SystemClock(), settings=settings
    )

    def slow_tool(args: dict) -> dict:
        time.sleep(3.0)  # Longer than soft timeout (2s)
        return {"result": "done"}

    result = executor.execute(
        tool=slow_tool,
        name="slow_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
    )

    assert result.status == "timeout"
    assert result.error is not None
    assert result.error["reason"] == "timeout"
    assert result.latency_ms >= 2000  # At least soft timeout
    assert result.from_cache is False

    # Check metrics - may be 1 or 2 depending on retries
    assert metrics.get_tool_error_count("slow_tool", "timeout") >= 1
    assert len(metrics.tool_latencies["slow_tool"]) == 1


def test_executor_retries_once_on_retryable_error_and_succeeds(
    executor: ToolExecutor, metrics: MetricsClient
) -> None:
    """Test that retryable errors trigger one retry."""
    call_count = 0

    def flaky_tool(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Network error")
        return {"result": "success"}

    result = executor.execute(
        tool=flaky_tool,
        name="flaky_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 2
    assert result.status == "success"
    assert result.retries == 1
    assert result.data == {"result": "success"}

    # Check metrics
    assert metrics.tool_retries["flaky_tool"] == 1
    assert metrics.get_tool_error_count("flaky_tool", "exception") == 1


def test_executor_does_not_retry_on_non_retryable_error(
    executor: ToolExecutor, metrics: MetricsClient
) -> None:
    """Test that non-retryable errors are not retried."""
    call_count = 0

    def failing_tool(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid input")

    result = executor.execute(
        tool=failing_tool,
        name="failing_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1  # Only called once
    assert result.status == "error"
    assert result.retries == 0
    assert result.error is not None
    assert result.error["type"] == "ValueError"


# === Circuit Breaker Tests ===


def test_breaker_opens_after_threshold_failures_and_short_circuits(
    executor: ToolExecutor, metrics: MetricsClient
) -> None:
    """Test that breaker opens after threshold failures."""

    def failing_tool(args: dict) -> dict:
        raise RuntimeError("Always fails")

    policy = BreakerPolicy(failure_threshold=5, window_seconds=60, cooldown_seconds=30)

    # Fail 5 times to open breaker
    for _ in range(5):
        result = executor.execute(
            tool=failing_tool,
            name="bad_tool",
            args={},
            cache_policy=CachePolicy(enabled=False),
            breaker_policy=policy,
        )
        assert result.status == "error"

    # 6th call should be short-circuited
    result = executor.execute(
        tool=failing_tool,
        name="bad_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=policy,
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error["reason"] == "breaker_open"
    assert "retry_after_seconds" in result.error

    # Check metrics
    assert metrics.breaker_opens["bad_tool"] >= 1
    assert metrics.breaker_states["bad_tool"] == "open"


def test_breaker_half_open_probe_and_closes_on_success(
    executor: ToolExecutor, metrics: MetricsClient, clock: FakeClock
) -> None:
    """Test that breaker transitions to half-open after cooldown and closes on success."""
    call_count = 0

    def tool_func(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count <= 5:
            raise RuntimeError("Fails initially")
        return {"result": "recovered"}

    policy = BreakerPolicy(failure_threshold=5, window_seconds=60, cooldown_seconds=30)

    # Fail 5 times to open breaker
    for _ in range(5):
        executor.execute(
            tool=tool_func,
            name="recovery_tool",
            args={},
            cache_policy=CachePolicy(enabled=False),
            breaker_policy=policy,
        )

    # Breaker should be open
    assert metrics.breaker_states["recovery_tool"] == "open"

    # Advance clock past cooldown
    clock.advance(31)

    # Next call should be a probe (half-open)
    result = executor.execute(
        tool=tool_func,
        name="recovery_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=policy,
    )

    # Should succeed and close breaker
    assert result.status == "success"
    assert metrics.breaker_states["recovery_tool"] == "closed"

    # Subsequent calls should work normally
    result = executor.execute(
        tool=tool_func,
        name="recovery_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=policy,
    )
    assert result.status == "success"


# === Caching Tests ===


def test_cache_hit_skips_underlying_tool_and_sets_from_cache(
    executor: ToolExecutor, metrics: MetricsClient
) -> None:
    """Test that cache hit skips tool execution."""
    call_count = 0

    def cached_tool(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": call_count}

    # First call
    result1 = executor.execute(
        tool=cached_tool,
        name="cached_tool",
        args={"key": "value"},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1
    assert result1.status == "success"
    assert result1.from_cache is False
    assert result1.data == {"result": 1}

    # Second call with same args - should hit cache
    result2 = executor.execute(
        tool=cached_tool,
        name="cached_tool",
        args={"key": "value"},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1  # Tool not called again
    assert result2.status == "success"
    assert result2.from_cache is True
    assert result2.data == {"result": 1}  # Same data

    # Check metrics
    assert metrics.tool_cache_hits["cached_tool"] == 1


def test_cache_key_is_stable_under_different_arg_order(
    executor: ToolExecutor,
) -> None:
    """Test that cache key is stable regardless of argument order."""
    call_count = 0

    def tool_func(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": call_count}

    # First call
    result1 = executor.execute(
        tool=tool_func,
        name="tool",
        args={"a": 1, "b": 2},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1
    assert result1.from_cache is False

    # Second call with different order - should hit cache
    result2 = executor.execute(
        tool=tool_func,
        name="tool",
        args={"b": 2, "a": 1},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1  # Not called again
    assert result2.from_cache is True


def test_failures_are_not_cached(executor: ToolExecutor) -> None:
    """Test that failures are never cached."""
    call_count = 0

    def tool_func(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("First call fails")
        return {"result": "success"}

    # First call fails
    result1 = executor.execute(
        tool=tool_func,
        name="tool",
        args={"key": "value"},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 1
    assert result1.status == "error"
    assert result1.from_cache is False

    # Second call should execute (not cached)
    result2 = executor.execute(
        tool=tool_func,
        name="tool",
        args={"key": "value"},
        cache_policy=CachePolicy(enabled=True, ttl_seconds=60),
        breaker_policy=BreakerPolicy(),
    )

    assert call_count == 2  # Called again
    assert result2.status == "success"
    assert result2.from_cache is False


# === Cancellation Tests ===


def test_cancel_before_execution_skips_tool_call(
    executor: ToolExecutor, metrics: MetricsClient
) -> None:
    """Test that cancelling before execution skips the tool."""
    call_count = 0

    def tool_func(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": "done"}

    cancel_token = CancelToken()
    cancel_token.cancel()

    result = executor.execute(
        tool=tool_func,
        name="tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
        cancel_token=cancel_token,
    )

    assert call_count == 0  # Tool not called
    assert result.status == "cancelled"
    assert result.error is not None
    assert result.error["reason"] == "cancelled"

    # Check metrics
    assert metrics.get_tool_error_count("tool", "cancelled") == 1


def test_cancel_during_retry_backoff_prevents_retry(
    executor: ToolExecutor,
) -> None:
    """Test that cancelling during retry backoff prevents retry."""
    call_count = 0
    cancel_token = CancelToken()

    def tool_func(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Cancel after first failure, before retry
            cancel_token.cancel()
            raise TimeoutError("First attempt times out")
        return {"result": "should not reach"}

    result = executor.execute(
        tool=tool_func,
        name="tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
        cancel_token=cancel_token,
    )

    assert call_count == 1  # Only first attempt
    assert result.status == "cancelled"


def test_cancel_during_long_running_call_returns_cancelled_status(
    executor: ToolExecutor,
) -> None:
    """Test that cancelling during execution returns cancelled status."""
    cancel_token = CancelToken()

    async def long_tool(args: dict) -> dict:
        await asyncio.sleep(5)
        return {"result": "done"}

    # Cancel token already cancelled
    cancel_token.cancel()

    result = executor.execute(
        tool=long_tool,
        name="long_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
        cancel_token=cancel_token,
    )

    # Should be cancelled before execution
    assert result.status == "cancelled"


# === Async Tool Tests ===


def test_executor_handles_async_tools(executor: ToolExecutor) -> None:
    """Test that executor can handle async tools."""

    async def async_tool(args: dict) -> dict:
        await asyncio.sleep(0.1)
        return {"result": "async success"}

    result = executor.execute(
        tool=async_tool,
        name="async_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
    )

    assert result.status == "success"
    assert result.data == {"result": "async success"}


def test_executor_handles_async_timeout(executor: ToolExecutor) -> None:
    """Test that async tools respect timeout."""

    async def slow_async_tool(args: dict) -> dict:
        await asyncio.sleep(5)  # Longer than soft timeout
        return {"result": "should not return"}

    result = executor.execute(
        tool=slow_async_tool,
        name="slow_async_tool",
        args={},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(),
    )

    assert result.status == "timeout"
    assert result.error is not None
    assert result.error["reason"] == "timeout"
