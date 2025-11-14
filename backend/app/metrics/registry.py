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

        # Verifier metrics (PR7)
        # Violation counts: kind -> count
        self.violation_counts: dict[str, int] = defaultdict(int)

        # Budget deltas: list of (budget_usd_cents, total_cost_usd_cents, delta)
        self.budget_deltas: list[tuple[int, int, int]] = []

        # Feasibility violation details: type -> count
        self.feasibility_violations: dict[str, int] = defaultdict(int)

        # Weather violation details: blocking vs advisory
        self.weather_blocking_total: int = 0
        self.weather_advisory_total: int = 0

        # Preference violations: preference -> count
        self.pref_violations: dict[str, int] = defaultdict(int)

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

    def observe_budget_delta(
        self, budget_usd_cents: int, total_cost_usd_cents: int
    ) -> None:
        """Record budget delta for metrics."""
        delta = total_cost_usd_cents - budget_usd_cents
        self.budget_deltas.append((budget_usd_cents, total_cost_usd_cents, delta))

    def inc_violation(self, kind: str) -> None:
        """Increment violation counter for a kind."""
        self.violation_counts[kind] += 1

    def inc_feasibility_violation(self, violation_type: str) -> None:
        """Increment feasibility violation counter by type."""
        self.feasibility_violations[violation_type] += 1

    def inc_weather_blocking(self) -> None:
        """Increment weather blocking violation counter."""
        self.weather_blocking_total += 1

    def inc_weather_advisory(self) -> None:
        """Increment weather advisory violation counter."""
        self.weather_advisory_total += 1

    def inc_pref_violation(self, preference: str) -> None:
        """Increment preference violation counter."""
        self.pref_violations[preference] += 1

    def get_budget_delta_stats(self) -> dict[str, float]:
        """Get budget delta statistics."""
        if not self.budget_deltas:
            return {"count": 0, "min": 0, "max": 0, "avg": 0}

        deltas = [delta for _, _, delta in self.budget_deltas]
        return {
            "count": len(deltas),
            "min": min(deltas),
            "max": max(deltas),
            "avg": sum(deltas) / len(deltas),
        }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.tool_latencies.clear()
        self.tool_retries.clear()
        self.tool_errors.clear()
        self.tool_cache_hits.clear()
        self.breaker_opens.clear()
        self.breaker_states.clear()
        # PR7 metrics
        self.violation_counts.clear()
        self.budget_deltas.clear()
        self.feasibility_violations.clear()
        self.weather_blocking_total = 0
        self.weather_advisory_total = 0
        self.pref_violations.clear()
