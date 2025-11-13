"""Unit tests for MetricsClient."""

import pytest

from backend.app.metrics import MetricsClient


@pytest.fixture
def metrics() -> MetricsClient:
    """Create a fresh metrics client."""
    return MetricsClient()


def test_observe_tool_latency_records_data(metrics: MetricsClient) -> None:
    """Test that latency observations are recorded."""
    metrics.observe_tool_latency("tool1", "success", 100)
    metrics.observe_tool_latency("tool1", "success", 200)
    metrics.observe_tool_latency("tool1", "error", 150)

    assert len(metrics.tool_latencies["tool1"]) == 3
    assert ("success", 100) in metrics.tool_latencies["tool1"]
    assert ("success", 200) in metrics.tool_latencies["tool1"]
    assert ("error", 150) in metrics.tool_latencies["tool1"]


def test_get_tool_latency_stats_calculates_correctly(metrics: MetricsClient) -> None:
    """Test that latency stats are calculated correctly."""
    metrics.observe_tool_latency("tool1", "success", 100)
    metrics.observe_tool_latency("tool1", "success", 200)
    metrics.observe_tool_latency("tool1", "success", 300)

    stats = metrics.get_tool_latency_stats("tool1")
    assert stats["count"] == 3
    assert stats["min"] == 100
    assert stats["max"] == 300
    assert stats["avg"] == 200


def test_get_tool_latency_stats_empty(metrics: MetricsClient) -> None:
    """Test latency stats for tool with no observations."""
    stats = metrics.get_tool_latency_stats("nonexistent")
    assert stats["count"] == 0
    assert stats["min"] == 0
    assert stats["max"] == 0
    assert stats["avg"] == 0


def test_inc_tool_retries_increments_counter(metrics: MetricsClient) -> None:
    """Test that retry counter increments."""
    metrics.inc_tool_retries("tool1", 1)
    metrics.inc_tool_retries("tool1", 2)

    assert metrics.tool_retries["tool1"] == 3


def test_inc_tool_errors_tracks_by_reason(metrics: MetricsClient) -> None:
    """Test that errors are tracked by reason."""
    metrics.inc_tool_errors("tool1", "timeout")
    metrics.inc_tool_errors("tool1", "timeout")
    metrics.inc_tool_errors("tool1", "breaker_open")

    assert metrics.tool_errors["tool1"]["timeout"] == 2
    assert metrics.tool_errors["tool1"]["breaker_open"] == 1


def test_get_tool_error_count_filters_by_reason(metrics: MetricsClient) -> None:
    """Test getting error count with optional reason filter."""
    metrics.inc_tool_errors("tool1", "timeout")
    metrics.inc_tool_errors("tool1", "timeout")
    metrics.inc_tool_errors("tool1", "breaker_open")

    assert metrics.get_tool_error_count("tool1", "timeout") == 2
    assert metrics.get_tool_error_count("tool1", "breaker_open") == 1
    assert metrics.get_tool_error_count("tool1") == 3  # Total


def test_inc_tool_cache_hit_increments(metrics: MetricsClient) -> None:
    """Test that cache hits are counted."""
    metrics.inc_tool_cache_hit("tool1")
    metrics.inc_tool_cache_hit("tool1")

    assert metrics.tool_cache_hits["tool1"] == 2


def test_inc_breaker_open_increments(metrics: MetricsClient) -> None:
    """Test that breaker open events are counted."""
    metrics.inc_breaker_open("tool1")
    metrics.inc_breaker_open("tool1")

    assert metrics.breaker_opens["tool1"] == 2


def test_set_breaker_state_updates_state(metrics: MetricsClient) -> None:
    """Test that breaker state is tracked."""
    metrics.set_breaker_state("tool1", "closed")
    assert metrics.breaker_states["tool1"] == "closed"

    metrics.set_breaker_state("tool1", "open")
    assert metrics.breaker_states["tool1"] == "open"

    metrics.set_breaker_state("tool1", "half_open")
    assert metrics.breaker_states["tool1"] == "half_open"


def test_reset_clears_all_metrics(metrics: MetricsClient) -> None:
    """Test that reset clears all metrics."""
    # Add some data
    metrics.observe_tool_latency("tool1", "success", 100)
    metrics.inc_tool_retries("tool1", 1)
    metrics.inc_tool_errors("tool1", "timeout")
    metrics.inc_tool_cache_hit("tool1")
    metrics.inc_breaker_open("tool1")
    metrics.set_breaker_state("tool1", "open")

    # Reset
    metrics.reset()

    # Verify all cleared
    assert len(metrics.tool_latencies) == 0
    assert len(metrics.tool_retries) == 0
    assert len(metrics.tool_errors) == 0
    assert len(metrics.tool_cache_hits) == 0
    assert len(metrics.breaker_opens) == 0
    assert len(metrics.breaker_states) == 0


def test_multiple_tools_tracked_independently(metrics: MetricsClient) -> None:
    """Test that different tools are tracked independently."""
    metrics.observe_tool_latency("tool1", "success", 100)
    metrics.observe_tool_latency("tool2", "success", 200)
    metrics.inc_tool_retries("tool1", 1)
    metrics.inc_tool_retries("tool2", 2)

    assert len(metrics.tool_latencies["tool1"]) == 1
    assert len(metrics.tool_latencies["tool2"]) == 1
    assert metrics.tool_retries["tool1"] == 1
    assert metrics.tool_retries["tool2"] == 2
