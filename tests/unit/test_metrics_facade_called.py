"""Tests for metrics façade being called correctly."""

import random
from typing import Any
from unittest.mock import patch

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.executor import InMemoryCache, ToolExecutor
from backend.app.exec.types import ToolName, ToolRequest


class SuccessRegistry:
    """Registry with tool that always succeeds."""

    def get_tool(self, name: ToolName):
        def success_tool(args: dict[str, Any]) -> dict[str, Any]:
            return {"result": "success"}

        return success_tool


class FailRegistry:
    """Registry with tool that always fails."""

    def get_tool(self, name: ToolName):
        def fail_tool(args: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("Tool error")

        return fail_tool


def test_metrics_called_on_success():
    """Test that metrics are recorded on successful execution."""
    settings = Settings()
    registry = SuccessRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )
    ctx = RunContext("test-run")

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        response = executor.execute(request, ctx)

        assert response.ok is True

        # Verify metrics called exactly once
        mock_metrics.assert_called_once()

        # Verify correct parameters
        call_kwargs = mock_metrics.call_args[1]
        assert call_kwargs["tool"] == "weather"
        assert call_kwargs["ok"] is True
        assert call_kwargs["from_cache"] is False
        assert call_kwargs["retries"] == 0
        assert call_kwargs["error_kind"] is None
        assert call_kwargs["latency_ms"] >= 0


def test_metrics_called_on_failure():
    """Test that metrics are recorded on failed execution."""
    settings = Settings()
    settings.soft_timeout_s = 0.5
    settings.hard_timeout_s = 1.0

    registry = FailRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )
    ctx = RunContext("test-run")

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        response = executor.execute(request, ctx)

        assert response.ok is False

        # Verify metrics called exactly once
        mock_metrics.assert_called_once()

        # Verify correct parameters
        call_kwargs = mock_metrics.call_args[1]
        assert call_kwargs["tool"] == "weather"
        assert call_kwargs["ok"] is False
        assert call_kwargs["from_cache"] is False
        assert call_kwargs["retries"] == 1  # Should have retried
        assert call_kwargs["error_kind"] == "tool_error"
        assert call_kwargs["latency_ms"] > 0


def test_metrics_called_on_cache_hit():
    """Test that metrics are recorded on cache hit."""
    settings = Settings()
    registry = SuccessRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        # First call - cache miss
        ctx1 = RunContext("test-run-1")
        executor.execute(request, ctx1)

        # Second call - cache hit
        ctx2 = RunContext("test-run-2")
        response = executor.execute(request, ctx2)

        assert response.from_cache is True

        # Metrics should be called twice (once per execute)
        assert mock_metrics.call_count == 2

        # Second call should indicate cache hit
        second_call_kwargs = mock_metrics.call_args_list[1][1]
        assert second_call_kwargs["tool"] == "weather"
        assert second_call_kwargs["ok"] is True
        assert second_call_kwargs["from_cache"] is True
        assert second_call_kwargs["retries"] == 0
        assert second_call_kwargs["error_kind"] is None


def test_metrics_called_on_breaker_open():
    """Test that metrics are recorded when circuit breaker is open."""
    settings = Settings()
    settings.breaker_failure_threshold = 5
    settings.soft_timeout_s = 0.5
    settings.hard_timeout_s = 1.0

    registry = FailRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        # Open the breaker with 5 failures
        for i in range(5):
            request = ToolRequest(
                name="weather",
                args={"lat": 48.8566, "lon": 2.3522},
                trace_id=f"test-trace-{i}",
                run_id=f"test-run-{i}",
            )
            ctx = RunContext(f"test-run-{i}")
            executor.execute(request, ctx)

        # Next call should hit open breaker
        request = ToolRequest(
            name="weather",
            args={"lat": 48.8566, "lon": 2.3522},
            trace_id="test-trace-breaker",
            run_id="test-run-breaker",
        )
        ctx = RunContext("test-run-breaker")
        response = executor.execute(request, ctx)

        assert response.breaker_open is True

        # Metrics should be called 6 times (5 failures + 1 breaker open)
        assert mock_metrics.call_count == 6

        # Last call should indicate breaker open
        last_call_kwargs = mock_metrics.call_args[1]
        assert last_call_kwargs["tool"] == "weather"
        assert last_call_kwargs["ok"] is False
        assert last_call_kwargs["error_kind"] == "breaker_open"
        assert last_call_kwargs["retries"] == 0


def test_metrics_called_on_cancellation():
    """Test that metrics are recorded on cancellation."""
    settings = Settings()
    registry = SuccessRegistry()
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

        assert response.error == "cancelled"

        # Metrics should still be called
        mock_metrics.assert_called_once()

        call_kwargs = mock_metrics.call_args[1]
        assert call_kwargs["tool"] == "weather"
        assert call_kwargs["ok"] is False
        assert call_kwargs["retries"] == 0


def test_metrics_called_exactly_once_per_execute():
    """Test that metrics are called exactly once per execute, regardless of path."""
    settings = Settings()
    registry = SuccessRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    request = ToolRequest(
        name="weather",
        args={"lat": 48.8566, "lon": 2.3522},
        trace_id="test-trace",
        run_id="test-run",
    )

    with patch("backend.app.exec.executor.record_tool_call") as mock_metrics:
        # Execute 3 times
        for i in range(3):
            ctx = RunContext(f"test-run-{i}")
            executor.execute(request, ctx)

        # Metrics should be called exactly 3 times
        assert mock_metrics.call_count == 3
