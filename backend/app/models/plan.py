"""Plan models representing the generated travel plan."""

from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import ChoiceKind, Provenance, TimeWindow


class ChoiceFeatures(BaseModel):
    """Required features extracted from choices for fast access."""

    cost_usd_cents: int = Field(description="Cost in cents")
    travel_seconds: int | None = Field(
        default=None, description="Travel time in seconds"
    )
    indoor: bool | None = Field(
        default=None, description="Tri-state: True=indoor, False=outdoor, None=unknown"
    )
    themes: list[str] | None = Field(default=None, description="Activity themes")


class Choice(BaseModel):
    """A ranked alternative for a slot."""

    kind: ChoiceKind = Field(description="Type of choice")
    option_ref: str = Field(description="Reference to detailed option data")
    features: ChoiceFeatures = Field(description="Extracted features for scoring")
    score: float | None = Field(default=None, description="Selection score")
    provenance: Provenance = Field(description="Data source information")


class Slot(BaseModel):
    """Time slot with ranked choice alternatives."""

    window: TimeWindow = Field(description="Time window for this slot")
    choices: list[Choice] = Field(description="Ranked alternatives (first is selected)")
    locked: bool = Field(default=False, description="Whether this slot is user-locked")

    @field_validator("choices")
    @classmethod
    def validate_non_empty_choices(cls, v: list[Choice]) -> list[Choice]:
        """Ensure at least one choice is provided."""
        if not v:
            raise ValueError("At least one choice must be provided")
        return v


class DayPlan(BaseModel):
    """Plan for a single day."""

    date: Date = Field(description="Date for this day's plan")
    slots: list[Slot] = Field(description="Time slots for the day")

    @model_validator(mode="after")
    def validate_non_overlapping_slots(self) -> DayPlan:
        """Ensure slots don't overlap."""
        sorted_slots = sorted(self.slots, key=lambda s: s.window.start)

        for i in range(len(sorted_slots) - 1):
            current_end = sorted_slots[i].window.end
            next_start = sorted_slots[i + 1].window.start

            if current_end > next_start:
                raise ValueError(
                    f"Overlapping slots: slot ending at {current_end} "
                    f"overlaps with slot starting at {next_start}"
                )

        return self


class Assumptions(BaseModel):
    """Planning assumptions and constants."""

    fx_rate_usd_eur: float = Field(description="USD to EUR exchange rate")
    daily_spend_est_cents: int = Field(description="Estimated daily spending in cents")
    transit_buffer_minutes: int = Field(
        default=15, description="Buffer time for transit connections"
    )
    airport_buffer_minutes: int = Field(
        default=120, description="Buffer time for airport connections"
    )


class PlanV1(BaseModel):
    """Generated travel plan."""

    days: list[DayPlan] = Field(description="Daily plans")
    assumptions: Assumptions = Field(description="Planning assumptions")
    rng_seed: int = Field(description="Random seed for reproducibility")

    @field_validator("days")
    @classmethod
    def validate_day_count(cls, v: list[DayPlan]) -> list[DayPlan]:
        """Validate the days list."""
        return v
