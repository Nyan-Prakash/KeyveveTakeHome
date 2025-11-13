"""In-process metrics registry for tool execution."""

from collections import defaultdict
from typing import Literal


class MetricsClient:
    """
    Simple in-process metrics client for tracking tool execution.

    Stores metrics in memory for testing and internal monitoring.
    Can be replaced with Prometheus/OpenTelemetry in the future.
    """

    def __init__(self) -> None:
        # Tool latency observations: tool -> list of (status, latency_ms)
        self.tool_latencies: dict[str, list[tuple[str, int]]] = defaultdict(list)

        # Retry counts: tool -> count
        self.tool_retries: dict[str, int] = defaultdict(int)

        # Error counts: tool -> reason -> count
        self.tool_errors: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Cache hits: tool -> count
        self.tool_cache_hits: dict[str, int] = defaultdict(int)

        # Breaker open events: tool -> count
        self.breaker_opens: dict[str, int] = defaultdict(int)

        # Breaker states: tool -> current state
        self.breaker_states: dict[str, Literal["open", "closed", "half_open"]] = {}

    def observe_tool_latency(self, tool: str, status: str, latency_ms: int) -> None:
        """Record a tool latency observation."""
        self.tool_latencies[tool].append((status, latency_ms))

    def inc_tool_retries(self, tool: str, count: int = 1) -> None:
        """Increment retry counter for a tool."""
        self.tool_retries[tool] += count

    def inc_tool_errors(self, tool: str, reason: str) -> None:
        """Increment error counter for a tool and reason."""
        self.tool_errors[tool][reason] += 1

    def inc_tool_cache_hit(self, tool: str) -> None:
        """Increment cache hit counter for a tool."""
        self.tool_cache_hits[tool] += 1

    def inc_breaker_open(self, tool: str) -> None:
        """Increment breaker open event counter."""
        self.breaker_opens[tool] += 1

    def set_breaker_state(
        self, tool: str, state: Literal["open", "closed", "half_open"]
    ) -> None:
        """Set current breaker state for a tool."""
        self.breaker_states[tool] = state

    def get_tool_latency_stats(self, tool: str) -> dict[str, float]:
        """Get latency statistics for a tool."""
        latencies = [lat for _, lat in self.tool_latencies.get(tool, [])]
        if not latencies:
            return {"count": 0, "min": 0, "max": 0, "avg": 0}

        return {
            "count": len(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "avg": sum(latencies) / len(latencies),
        }

    def get_tool_error_count(self, tool: str, reason: str | None = None) -> int:
        """Get error count for a tool, optionally filtered by reason."""
        if reason:
            return self.tool_errors.get(tool, {}).get(reason, 0)
        return sum(self.tool_errors.get(tool, {}).values())

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.tool_latencies.clear()
        self.tool_retries.clear()
        self.tool_errors.clear()
        self.tool_cache_hits.clear()
        self.breaker_opens.clear()
        self.breaker_states.clear()
