"""Tests for executor cancellation behavior."""

import random
import threading
import time
from typing import Any
from unittest.mock import patch

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.executor import InMemoryCache, ToolExecutor
from backend.app.exec.types import ToolName, ToolRequest


class SimpleRegistry:
    """Simple registry for testing."""

    def __init__(self) -> None:
        """Initialize registry."""
        self.call_count = 0

    def get_tool(self, name: ToolName):
        """Get simple tool."""

        def simple_tool(args: dict[str, Any]) -> dict[str, Any]:
            """Simple tool that returns success."""
            self.call_count += 1
            return {"result": "success"}

        return simple_tool


def test_cancellation_before_execute():
    """Test that cancellation before execute prevents tool invocation."""
    settings = Settings()
    registry = SimpleRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    # Create context and set cancelled before execute
    ctx = RunContext("test-run")
    ctx.cancelled.set()

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        response = executor.execute(request, ctx)

        # Should return cancelled response without calling tool
        assert response.ok is False
        assert response.error == "cancelled"
        assert response.retries == 0
        assert response.from_cache is False
        assert response.breaker_open is False
        assert registry.call_count == 0, "Tool should not be called when cancelled"

        # Metrics should still be recorded
        mock_metrics.assert_called_once()


def test_cancellation_between_attempts():
    """Test that cancellation between attempts skips retry."""

    class TimeoutOnceRegistry:
        """Registry with tool that times out on first call."""

        def __init__(self, cancel_event: threading.Event) -> None:
            self.call_count = 0
            self.cancel_event = cancel_event

        def get_tool(self, name: ToolName):
            def timeout_once_tool(args: dict[str, Any]) -> dict[str, Any]:
                self.call_count += 1
                if self.call_count == 1:
                    # During first call, set cancel flag then timeout
                    time.sleep(0.1)
                    self.cancel_event.set()
                    time.sleep(1.5)  # This will timeout
                return {"result": "success"}

            return timeout_once_tool

    settings = Settings()
    settings.soft_timeout_s = 1.0
    settings.hard_timeout_s = 4.0
    settings.retry_jitter_min_ms = 50
    settings.retry_jitter_max_ms = 100

    ctx = RunContext("test-run")
    registry = TimeoutOnceRegistry(ctx.cancelled)
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    with patch("backend.app.exec.executor.record_tool_call"):
        response = executor.execute(request, ctx)

        # Should be cancelled, not retry
        assert response.ok is False
        assert response.error == "cancelled"
        # Tool called once (first attempt), but not retried
        assert registry.call_count == 1, "Should not retry after cancellation"


def test_normal_execution_without_cancellation():
    """Test that normal execution works when not cancelled."""
    settings = Settings()
    registry = SimpleRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    ctx = RunContext("test-run")

    with patch("backend.app.exec.executor.record_tool_call"):
        response = executor.execute(request, ctx)

        # Should succeed normally
        assert response.ok is True
        assert response.error is None
        assert response.data == {"result": "success"}
        assert registry.call_count == 1


def test_cancellation_does_not_affect_metrics():
    """Test that metrics are still recorded on cancellation."""
    settings = Settings()
    registry = SimpleRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    ctx = RunContext("test-run")
    ctx.cancelled.set()

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        response = executor.execute(request, ctx)

        assert response.ok is False
        assert response.error == "cancelled"

        # Metrics should be recorded
        mock_metrics.assert_called_once()
        call_args = mock_metrics.call_args
        assert call_args[1]["ok"] is False
        assert call_args[1]["retries"] == 0
