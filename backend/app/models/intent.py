"""Intent models representing user travel preferences."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .common import TimeWindow


class DateWindow(BaseModel):
    """Date range for travel with timezone."""

    start: date = Field(description="Earliest departure date")
    end: date = Field(description="Latest return date (inclusive)")
    tz: str = Field(description="IANA timezone, e.g. 'Europe/Paris'")

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v: date, info: ValidationInfo) -> date:
        """Ensure end date is not before start date."""
        if "start" in info.data and v < info.data["start"]:
            raise ValueError("End date must be on or after start date")
        return v


class LockedSlot(BaseModel):
    """User-pinned activity that cannot be changed during planning."""

    day_offset: int = Field(description="0-indexed day from trip start")
    window: TimeWindow = Field(description="Time window for the locked activity")
    activity_id: str = Field(description="ID of the locked activity")


class Preferences(BaseModel):
    """User preferences for trip planning."""

    kid_friendly: bool = Field(
        default=False, description="Whether trip is kid-friendly"
    )
    themes: list[str] = Field(
        default=[], description="Preferred themes (art, food, etc)"
    )
    avoid_overnight: bool = Field(default=False, description="Avoid red-eye flights")
    locked_slots: list[LockedSlot] = Field(
        default=[], description="User-pinned activities"
    )


class IntentV1(BaseModel):
    """User's travel intent and constraints."""

    city: str = Field(description="Destination city")
    date_window: DateWindow = Field(description="Travel date range")
    budget_usd_cents: int = Field(description="Total trip budget in cents")
    airports: list[str] = Field(description="IATA airport codes")
    prefs: Preferences = Field(description="User preferences")

    @field_validator("budget_usd_cents")
    @classmethod
    def validate_positive_budget(cls, v: int) -> int:
        """Ensure budget is positive."""
        if v <= 0:
            raise ValueError("Budget must be positive")
        return v

    @field_validator("airports")
    @classmethod
    def validate_non_empty_airports(cls, v: list[str]) -> list[str]:
        """Ensure at least one airport is provided."""
        if not v:
            raise ValueError("At least one airport must be provided")
        return v
