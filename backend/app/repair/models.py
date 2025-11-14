"""Repair models for PR8: bounded, explainable fixes."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from backend.app.models.common import Provenance
from backend.app.models.plan import PlanV1
from backend.app.models.violations import Violation


class MoveType(str, Enum):
    """Types of repair moves allowed."""

    change_hotel_tier = "change_hotel_tier"
    reorder_slots = "reorder_slots"
    replace_slot = "replace_slot"
    swap_airport = "swap_airport"


class RepairDiff(BaseModel):
    """Represents a single repair change with metrics."""

    move_type: MoveType = Field(description="Type of repair move applied")
    day_index: int = Field(description="Day index affected by this move")
    slot_index: int | None = Field(
        default=None, description="Slot index affected (if applicable)"
    )
    old_value: str = Field(description="Description of old value")
    new_value: str = Field(description="Description of new value")
    usd_delta_cents: int = Field(
        description="Change in total cost (negative = savings)"
    )
    minutes_delta: int = Field(description="Change in total travel time")
    reason: str = Field(description="Human-readable explanation for this change")
    provenance: Provenance = Field(description="Source of the replacement data")


class RepairResult(BaseModel):
    """Result of running the repair engine."""

    plan_before: PlanV1 = Field(description="Plan before repair")
    plan_after: PlanV1 = Field(description="Plan after repair")
    diffs: list[RepairDiff] = Field(description="List of changes made")
    remaining_violations: list[Violation] = Field(
        description="Violations that remain after repair"
    )
    cycles_run: int = Field(description="Number of repair cycles executed")
    moves_applied: int = Field(description="Total number of moves applied")
    reuse_ratio: float = Field(
        description="Fraction of slots unchanged (0-1)", ge=0.0, le=1.0
    )
    success: bool = Field(
        description="Whether all blocking violations were resolved"
    )
