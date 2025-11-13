"""Metrics façade for tool execution tracking."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.exec.types import ExecutorErrorKind

logger = logging.getLogger(__name__)


def record_tool_call(
    tool: str,
    latency_ms: int,
    ok: bool,
    from_cache: bool,
    retries: int,
    error_kind: "ExecutorErrorKind | None",
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd_cents: int | None = None,
) -> None:
    """Record metrics for a tool call.

    This is a simple stub implementation that logs metrics.
    In production, this would emit to Prometheus/OpenTelemetry.

    Args:
        tool: Name of the tool that was called.
        latency_ms: Latency in milliseconds.
        ok: Whether the call succeeded.
        from_cache: Whether the result came from cache.
        retries: Number of retries performed.
        error_kind: Type of error if call failed, None if succeeded.
        tokens_in: Optional token count for input.
        tokens_out: Optional token count for output.
        cost_usd_cents: Optional cost in USD cents.
    """
    logger.info(
        "tool_call_metric",
        extra={
            "tool": tool,
            "latency_ms": latency_ms,
            "ok": ok,
            "from_cache": from_cache,
            "retries": retries,
            "error_kind": error_kind,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd_cents": cost_usd_cents,
        },
    )
