"""Executor types and contracts."""

from typing import Any, Literal

from pydantic import BaseModel

ToolName = Literal[
    "weather",
    "flights",
    "lodging",
    "events",
    "transit",
    "fx",
    "geocode",
]

ExecutorErrorKind = Literal[
    "timeout_soft",
    "timeout_hard",
    "breaker_open",
    "tool_error",
]


class ToolRequest(BaseModel):
    """Request to execute a tool."""

    name: ToolName
    args: dict[str, Any]
    trace_id: str
    run_id: str
    timeout_soft_ms: int | None = None
    timeout_hard_ms: int | None = None


class ToolResponse(BaseModel):
    """Response from tool execution."""

    ok: bool
    data: dict[str, Any] | None
    error: str | None
    from_cache: bool
    latency_ms: int
    retries: int
    breaker_open: bool
