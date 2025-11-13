"""Tests for executor cache behavior."""

import random
from typing import Any
from unittest.mock import patch

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.executor import InMemoryCache, ToolExecutor
from backend.app.exec.types import ToolName, ToolRequest


class CountingRegistry:
    """Registry with tool that counts invocations."""

    def __init__(self) -> None:
        """Initialize registry."""
        self.call_count = 0

    def get_tool(self, name: ToolName):
        """Get tool that increments counter."""

        def counting_tool(args: dict[str, Any]) -> dict[str, Any]:
            """Tool that counts invocations."""
            self.call_count += 1
            return {"result": f"call_{self.call_count}", "count": self.call_count}

        return counting_tool


def test_executor_cache_hit():
    """Test that cache hit prevents tool invocation."""
    # Setup
    settings = Settings()
    registry = CountingRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        # First call - cache miss, tool should be called
        ctx1 = RunContext("test-run-1")
        response1 = executor.execute(request, ctx1)

        assert response1.ok is True
        assert response1.from_cache is False
        assert response1.data == {"result": "call_1", "count": 1}
        assert registry.call_count == 1, "Tool should be called once on cache miss"

        # Second call with identical request - cache hit, tool should NOT be called
        ctx2 = RunContext("test-run-2")
        response2 = executor.execute(request, ctx2)

        assert response2.ok is True
        assert response2.from_cache is True
        assert response2.data == {"result": "call_1", "count": 1}, "Should return cached data"
        assert registry.call_count == 1, "Tool should not be called again on cache hit"

        # Verify metrics were called twice (once for each execute)
        assert mock_metrics.call_count == 2
        # First call: from_cache=False
        assert mock_metrics.call_args_list[0][1]["from_cache"] is False
        # Second call: from_cache=True
        assert mock_metrics.call_args_list[1][1]["from_cache"] is True


def test_executor_cache_different_args():
    """Test that different args result in different cache keys."""
    settings = Settings()
    registry = CountingRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    with patch("backend.app.exec.executor.record_tool_call"):
        # First call with specific coordinates
        request1 = ToolRequest(
            name="weather",
            args={"lat": 48.8566, "lon": 2.3522},
            trace_id="test-trace-1",
            run_id="test-run-1",
        )
        ctx1 = RunContext("test-run-1")
        response1 = executor.execute(request1, ctx1)

        assert response1.ok is True
        assert registry.call_count == 1

        # Second call with different coordinates - should be cache miss
        request2 = ToolRequest(
            name="weather",
            args={"lat": 40.7128, "lon": -74.0060},  # Different location
            trace_id="test-trace-2",
            run_id="test-run-2",
        )
        ctx2 = RunContext("test-run-2")
        response2 = executor.execute(request2, ctx2)

        assert response2.ok is True
        assert response2.from_cache is False
        assert registry.call_count == 2, "Different args should result in cache miss"


def test_executor_cache_only_caches_success():
    """Test that only successful responses are cached."""

    class FailOnceRegistry:
        """Registry with tool that fails first time, succeeds second time."""

        def __init__(self) -> None:
            self.call_count = 0

        def get_tool(self, name: ToolName):
            def fail_once_tool(args: dict[str, Any]) -> dict[str, Any]:
                self.call_count += 1
                if self.call_count <= 2:  # Fail on first execution (2 attempts)
                    raise RuntimeError("First execution fails")
                return {"result": "success"}

            return fail_once_tool

    settings = Settings()
    settings.soft_timeout_s = 0.5
    settings.hard_timeout_s = 1.0

    registry = FailOnceRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    with patch("backend.app.exec.executor.record_tool_call"):
        # First call - should fail and NOT be cached
        ctx1 = RunContext("test-run-1")
        response1 = executor.execute(request, ctx1)

        assert response1.ok is False
        assert registry.call_count == 2  # Initial + retry

        # Second call - should succeed (tool invoked again, not from cache)
        ctx2 = RunContext("test-run-2")
        response2 = executor.execute(request, ctx2)

        assert response2.ok is True
        assert response2.from_cache is False
        assert registry.call_count == 3, "Failed response should not be cached"

        # Third call - should be cached now
        ctx3 = RunContext("test-run-3")
        response3 = executor.execute(request, ctx3)

        assert response3.ok is True
        assert response3.from_cache is True
        assert registry.call_count == 3, "Should use cached successful response"


def test_cache_key_deterministic():
    """Test that cache key is deterministic for same input."""
    settings = Settings()
    registry = CountingRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    # Two requests with same data but different order in args
    request1 = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522, "extra": "data"},
        trace_id="test-trace-1",
        run_id="test-run-1",
    )

    request2 = ToolRequest(
        name="weather",
        args={"lon": 2.3522, "extra": "data", "lat": 48.8566},  # Different order
        trace_id="test-trace-2",
        run_id="test-run-2",
    )

    key1 = executor._compute_cache_key(request1)
    key2 = executor._compute_cache_key(request2)

    assert key1 == key2, "Cache keys should be identical for same data in different order"
