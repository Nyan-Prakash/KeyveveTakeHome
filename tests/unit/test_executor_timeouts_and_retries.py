"""Tests for executor timeout and retry behavior."""

import random
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.executor import InMemoryCache, ToolExecutor
from backend.app.exec.types import ToolName, ToolRequest


class FakeRegistry:
    """Fake tool registry for testing."""

    def __init__(self) -> None:
        """Initialize fake registry."""
        self.call_count = 0
        self.call_times: list[float] = []

    def get_tool(self, name: ToolName):
        """Get fake tool function."""

        def fake_tool(args: dict[str, Any]) -> dict[str, Any]:
            """Fake tool that simulates timeout on first call."""
            self.call_count += 1
            self.call_times.append(time.time())

            # First call: simulate soft timeout (sleep > soft but < hard)
            if self.call_count == 1:
                time.sleep(2.5)  # Between soft (2s) and hard (4s)
                return {"result": "first_call"}

            # Second call: return quickly
            return {"result": "second_call_success"}

        return fake_tool


def test_executor_timeouts_and_retries():
    """Test that executor retries on timeout and succeeds on second attempt."""
    # Setup
    settings = Settings()
    settings.soft_timeout_s = 2.0
    settings.hard_timeout_s = 4.0
    settings.retry_jitter_min_ms = 200
    settings.retry_jitter_max_ms = 500

    registry = FakeRegistry()
    cache = InMemoryCache()
    rng = random.Random(42)  # Seeded for reproducibility
    executor = ToolExecutor(registry, settings, cache, rng)

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )
    ctx = RunContext("test-run")

    # Mock metrics to verify it's called
    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        start = time.time()
        response = executor.execute(request, ctx)
        elapsed = time.time() - start

        # Assertions
        assert response.ok is True, "Response should be successful"
        assert response.data == {"result": "second_call_success"}
        assert response.retries == 1, "Should have retried once"
        assert response.from_cache is False
        assert response.breaker_open is False
        assert registry.call_count == 2, "Tool should be invoked exactly twice"

        # Elapsed time should be bounded by hard timeout
        assert elapsed < settings.hard_timeout_s + 1.0, "Should not exceed hard timeout by much"

        # Metrics should be called exactly once
        mock_metrics.assert_called_once()
        call_args = mock_metrics.call_args
        assert call_args[1]["tool"] == "weather"
        assert call_args[1]["retries"] == 1
        assert call_args[1]["ok"] is True
        assert call_args[1]["error_kind"] is None


def test_executor_hard_timeout():
    """Test that executor respects hard timeout."""

    class SlowRegistry:
        """Registry with tool that always times out."""

        def get_tool(self, name: ToolName):
            def slow_tool(args: dict[str, Any]) -> dict[str, Any]:
                time.sleep(5.0)  # Longer than hard timeout
                return {"result": "never_reached"}

            return slow_tool

    settings = Settings()
    settings.soft_timeout_s = 2.0
    settings.hard_timeout_s = 4.0

    registry = SlowRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )
    ctx = RunContext("test-run")

    with patch("backend.app.exec.executor.record_tool_call"):
        start = time.time()
        response = executor.execute(request, ctx)
        elapsed = time.time() - start

        # Should fail due to timeout
        assert response.ok is False
        assert response.error == "timeout" or "timeout" in str(response.error)
        assert elapsed < 5.0, "Should not wait for full slow tool execution"
