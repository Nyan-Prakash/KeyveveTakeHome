"""Itinerary models for final travel output."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ChoiceKind, Geo, Provenance, TimeWindow
from .intent import IntentV1


class Activity(BaseModel):
    """A scheduled activity in the itinerary."""

    window: TimeWindow = Field(description="Time window for the activity")
    kind: ChoiceKind = Field(description="Type of activity")
    name: str = Field(description="Activity name")
    geo: Geo | None = Field(default=None, description="Activity location")
    notes: str = Field(description="Additional notes or details")
    locked: bool = Field(description="Whether this activity was user-locked")
    cost_usd_cents: int | None = Field(default=None, description="Activity cost in USD cents")


class DayItinerary(BaseModel):
    """Itinerary for a single day."""

    day_date: date = Field(description="Date for this day")
    activities: list[Activity] = Field(description="Scheduled activities")


class CostBreakdown(BaseModel):
    """Detailed cost breakdown for the trip."""

    flights_usd_cents: int = Field(description="Flight costs in cents")
    lodging_usd_cents: int = Field(description="Lodging costs in cents")
    attractions_usd_cents: int = Field(description="Attraction costs in cents")
    transit_usd_cents: int = Field(description="Transit costs in cents")
    daily_spend_usd_cents: int = Field(description="Daily spending costs in cents")
    total_usd_cents: int = Field(description="Total trip cost in cents")
    currency_disclaimer: str = Field(description="Exchange rate disclaimer")


class Decision(BaseModel):
    """A planning decision made during generation."""

    node: str = Field(description="Decision node identifier")
    rationale: str = Field(description="Reason for the decision")
    alternatives_considered: int = Field(description="Number of alternatives evaluated")
    selected: str = Field(description="Selected option identifier")


class Citation(BaseModel):
    """Citation linking claims to data sources."""

    claim: str = Field(description="The claim being cited")
    provenance: Provenance = Field(description="Source of the claim")


class ItineraryV1(BaseModel):
    """Complete travel itinerary output."""

    itinerary_id: str = Field(description="Unique itinerary identifier")
    intent: IntentV1 = Field(description="Original user intent")
    days: list[DayItinerary] = Field(description="Daily itineraries")
    cost_breakdown: CostBreakdown = Field(description="Cost breakdown")
    decisions: list[Decision] = Field(description="Planning decisions made")
    citations: list[Citation] = Field(description="Data source citations")
    created_at: datetime = Field(description="Itinerary creation timestamp")
    trace_id: str = Field(description="Tracing identifier")
