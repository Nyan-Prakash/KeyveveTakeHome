"""Violation models for plan verification."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .common import ViolationKind


class Violation(BaseModel):
    """A constraint violation in the plan."""

    kind: ViolationKind = Field(description="Type of violation")
    node_ref: str = Field(description="Reference to the violating node")
    details: dict[str, Any] = Field(description="Additional violation details")
    blocking: bool = Field(description="Whether this violation blocks plan completion")
