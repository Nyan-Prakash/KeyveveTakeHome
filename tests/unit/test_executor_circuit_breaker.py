"""Tests for executor circuit breaker behavior."""

import random
import time
from typing import Any
from unittest.mock import patch

from backend.app.config import Settings
from backend.app.exec.context import RunContext
from backend.app.exec.executor import InMemoryCache, ToolExecutor
from backend.app.exec.types import ToolName, ToolRequest


class FailingRegistry:
    """Registry with tool that always fails."""

    def __init__(self) -> None:
        """Initialize registry."""
        self.call_count = 0

    def get_tool(self, name: ToolName):
        """Get tool that raises an exception."""

        def failing_tool(args: dict[str, Any]) -> dict[str, Any]:
            """Tool that always fails."""
            self.call_count += 1
            raise RuntimeError("Tool failure")

        return failing_tool


def test_circuit_breaker_opens_after_threshold():
    """Test that circuit breaker opens after threshold failures."""
    # Setup
    settings = Settings()
    settings.breaker_failure_threshold = 5
    settings.breaker_timeout_s = 60
    settings.soft_timeout_s = 0.5  # Short timeout for faster test
    settings.hard_timeout_s = 1.0

    registry = FailingRegistry()
    cache = InMemoryCache()
    executor = ToolExecutor(registry, settings, cache, random.Random(42))

    with patch("backend.app.exec.executor.record_tool_call"):
        # Make 5 calls - all should invoke the tool and fail
        for i in range(5):
            request = ToolRequest(
                name="weather",
                args={"lat": 48.8566, "lon": 2.3522},
                trace_id=f"test-trace-{i}",
                run_id=f"test-run-{i}",
            )
            ctx = RunContext(f"test-run-{i}")
            response = executor.execute(request, ctx)

            # Should fail but breaker not open yet
            assert response.ok is False
            assert response.breaker_open is False
            # Tool is called twice per execution (initial + retry)
            expected_calls = (i + 1) * 2
            assert (
                registry.call_count == expected_calls
            ), f"Expected {expected_calls} calls, got {registry.call_count}"

        # 6th call - breaker should be open
        request = ToolRequest(
            name="weather",
            args={"lat": 48.8566, "lon": 2.3522},
            trace_id="test-trace-6",
            run_id="test-run-6",
        )
        ctx = RunContext("test-run-6")
        response = executor.execute(request, ctx)

        # Should fail with breaker open
        assert response.ok is False
        assert response.breaker_open is True
        assert response.error == "circuit_open"
        # Tool should NOT be invoked (still 10 calls from previous 5 executions)
        assert registry.call_count == 10, "Tool should not be called when breaker is open"


def test_circuit_breaker_half_open_probe_success():
    """Test that circuit breaker transitions to half-open and closes on success."""

    class ConditionalRegistry:
        """Registry with tool that fails first N times, then succeeds."""

        def __init__(self, fail_count: int) -> None:
            """Initialize registry.

            Args:
                fail_count: Number of times to fail before succeeding.
            """
            self.call_count = 0
            self.fail_count = fail_count

        def get_tool(self, name: ToolName):
            def conditional_tool(args: dict[str, Any]) -> dict[str, Any]:
                self.call_count += 1
                if self.call_count <= self.fail_count:
                    raise RuntimeError("Tool failure")
                return {"result": "success"}

            return conditional_tool

    settings = Settings()
    settings.breaker_failure_threshold = 5
    settings.breaker_timeout_s = 60
    settings.soft_timeout_s = 0.5
    settings.hard_timeout_s = 1.0

    # Fail 10 times (5 executions × 2 attempts each), then succeed
    registry = ConditionalRegistry(fail_count=10)
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    with patch("backend.app.exec.executor.record_tool_call"):
        # Make 5 failing calls to open the breaker
        for i in range(5):
            request = ToolRequest(
                name="weather",
                args={"lat": 48.8566, "lon": 2.3522},
                trace_id=f"test-trace-{i}",
                run_id=f"test-run-{i}",
            )
            ctx = RunContext(f"test-run-{i}")
            response = executor.execute(request, ctx)
            assert response.ok is False

        # Breaker should be open
        breaker = executor.breakers["weather"]
        assert breaker.state == "open"

        # Wait for half-open transition (30 seconds by default)
        # For testing, we'll manually transition to half-open
        breaker.state = "half_open"

        # Next call should probe
        request = ToolRequest(
            name="weather",
            args={"lat": 48.8566, "lon": 2.3522},
            trace_id="test-trace-probe",
            run_id="test-run-probe",
        )
        ctx = RunContext("test-run-probe")
        response = executor.execute(request, ctx)

        # Should succeed and close the breaker
        assert response.ok is True
        assert breaker.state == "closed"


def test_circuit_breaker_half_open_probe_failure():
    """Test that circuit breaker stays open on failed probe."""

    class AlwaysFailRegistry:
        """Registry with tool that always fails."""

        def get_tool(self, name: ToolName):
            def failing_tool(args: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Tool failure")

            return failing_tool

    settings = Settings()
    settings.breaker_failure_threshold = 5
    settings.soft_timeout_s = 0.5
    settings.hard_timeout_s = 1.0

    registry = AlwaysFailRegistry()
    executor = ToolExecutor(registry, settings, None, random.Random(42))

    with patch("backend.app.exec.executor.record_tool_call"):
        # Open the breaker
        for i in range(5):
            request = ToolRequest(
                name="weather",
                args={"lat": 48.8566, "lon": 2.3522},
                trace_id=f"test-trace-{i}",
                run_id=f"test-run-{i}",
            )
            ctx = RunContext(f"test-run-{i}")
            executor.execute(request, ctx)

        breaker = executor.breakers["weather"]
        assert breaker.state == "open"

        # Manually transition to half-open
        breaker.state = "half_open"

        # Probe should fail and return to open
        request = ToolRequest(
            name="weather",
            args={"lat": 48.8566, "lon": 2.3522},
            trace_id="test-trace-probe",
            run_id="test-run-probe",
        )
        ctx = RunContext("test-run-probe")
        response = executor.execute(request, ctx)

        assert response.ok is False
        assert breaker.state == "open"
