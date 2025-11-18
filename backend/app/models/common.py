"""Common data types and enums used across the application."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from enum import Enum
from typing import Any

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
    train = "train"


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


# Provenance helper functions


def compute_response_digest(data: Any) -> str:
    """
    Compute SHA256 digest of response data for deduplication.

    Args:
        data: Any JSON-serializable data

    Returns:
        Hex string digest of the data
    """
    # Convert to stable JSON representation
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def create_provenance(
    source: str,
    ref_id: str | None = None,
    source_url: str | None = None,
    fetched_at: datetime | None = None,
    cache_hit: bool | None = None,
    response_data: Any = None,
) -> Provenance:
    """
    Create a Provenance object with automatic timestamp and digest computation.

    Args:
        source: Data source type (tool, rag, user, fixture)
        ref_id: Optional reference ID for the data source
        source_url: Optional URL of the data source
        fetched_at: When data was fetched (defaults to now)
        cache_hit: Whether data came from cache
        response_data: Optional response data to compute digest from

    Returns:
        Provenance object with all fields populated
    """
    if fetched_at is None:
        fetched_at = datetime.now(UTC)

    response_digest = None
    if response_data is not None:
        response_digest = compute_response_digest(response_data)

    return Provenance(
        source=source,
        ref_id=ref_id,
        source_url=source_url,
        fetched_at=fetched_at,
        cache_hit=cache_hit,
        response_digest=response_digest,
    )
