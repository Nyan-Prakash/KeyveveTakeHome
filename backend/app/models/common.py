"""Common data types and enums used across the application."""

from __future__ import annotations

from datetime import datetime, time
from enum import Enum

from pydantic import BaseModel, Field


class Geo(BaseModel):
    """Geographic coordinates in WGS84 decimal degrees."""

    lat: float = Field(description="Latitude in decimal degrees")
    lon: float = Field(description="Longitude in decimal degrees")


class TimeWindow(BaseModel):
    """Time window in local time."""

    start: time = Field(description="Start time in local time")
    end: time = Field(description="End time in local time")


class Money(BaseModel):
    """Monetary amount stored as integer cents."""

    amount_cents: int = Field(description="Amount in cents")
    currency: str = Field(default="USD", description="Currency code")


class ChoiceKind(str, Enum):
    """Type of choice in a slot."""

    flight = "flight"
    lodging = "lodging"
    attraction = "attraction"
    transit = "transit"
    meal = "meal"


class Tier(str, Enum):
    """Service tier levels."""

    budget = "budget"
    mid = "mid"
    luxury = "luxury"


class TransitMode(str, Enum):
    """Transportation modes."""

    walk = "walk"
    metro = "metro"
    bus = "bus"
    taxi = "taxi"


class ViolationKind(str, Enum):
    """Types of plan violations."""

    budget_exceeded = "budget_exceeded"
    timing_infeasible = "timing_infeasible"
    venue_closed = "venue_closed"
    weather_unsuitable = "weather_unsuitable"
    pref_violated = "pref_violated"


class Provenance(BaseModel):
    """Tracks the source and freshness of data."""

    source: str = Field(description="Data source type: tool, rag, user")
    ref_id: str | None = Field(
        default=None, description="Reference ID for the data source"
    )
    source_url: str | None = Field(default=None, description="URL of the data source")
    fetched_at: datetime = Field(description="When the data was fetched")
    cache_hit: bool | None = Field(
        default=None, description="Whether data came from cache"
    )
    response_digest: str | None = Field(
        default=None, description="Hash of the response for deduplication"
    )
