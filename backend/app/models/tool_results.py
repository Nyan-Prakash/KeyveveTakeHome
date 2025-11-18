"""Models for tool results from external data sources."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field

from .common import Geo, Provenance, Tier, TimeWindow, TransitMode


class FlightOption(BaseModel):
    """Flight search result."""

    flight_id: str = Field(description="Unique flight identifier")
    origin: str = Field(description="Origin IATA code")
    dest: str = Field(description="Destination IATA code")
    departure: datetime = Field(description="Departure time in UTC")
    arrival: datetime = Field(description="Arrival time in UTC")
    duration_seconds: int = Field(description="Flight duration in seconds")
    price_usd_cents: int = Field(description="Price in USD cents")
    overnight: bool = Field(description="Whether this is an overnight flight")
    provenance: Provenance = Field(description="Data source information")


class Lodging(BaseModel):
    """Lodging search result."""

    lodging_id: str = Field(description="Unique lodging identifier")
    name: str = Field(description="Lodging name")
    geo: Geo = Field(description="Geographic coordinates")
    checkin_window: TimeWindow = Field(description="Check-in time window")
    checkout_window: TimeWindow = Field(description="Check-out time window")
    price_per_night_usd_cents: int = Field(description="Price per night in USD cents")
    tier: Tier = Field(description="Service tier")
    kid_friendly: bool = Field(description="Whether kid-friendly")
    provenance: Provenance = Field(description="Data source information")


class Window(BaseModel):
    """Opening hours window with timezone-aware times."""

    start: datetime = Field(description="Opening time (timezone-aware)")
    end: datetime = Field(description="Closing time (timezone-aware)")


class Attraction(BaseModel):
    """Attraction search result (V1 spec format)."""

    id: str = Field(description="Unique attraction identifier")
    name: str = Field(description="Attraction name")
    venue_type: str = Field(description="Type: museum, park, temple, other")
    indoor: bool | None = Field(
        default=None, description="Tri-state: True=indoor, False=outdoor, None=unknown"
    )
    kid_friendly: bool | None = Field(
        default=None,
        description="Tri-state: True=kid-friendly, False=not, None=unknown",
    )
    opening_hours: dict[str, list[Window]] = Field(
        description="Opening hours keyed by weekday '0'-'6' (Monday=0)"
    )
    location: Geo = Field(description="Geographic coordinates")
    est_price_usd_cents: int | None = Field(
        default=None, description="Estimated price in USD cents"
    )
    provenance: Provenance = Field(description="Data source information")


class WeatherDay(BaseModel):
    """Weather forecast for a single day."""

    forecast_date: date = Field(description="Forecast date")
    precip_prob: float = Field(
        default=0.0, description="Precipitation probability (0.0-1.0)"
    )
    wind_kmh: float = Field(default=0.0, description="Wind speed in km/h")
    temp_c_high: float = Field(default=0.0, description="High temperature in Celsius")
    temp_c_low: float = Field(default=0.0, description="Low temperature in Celsius")
    city: str | None = Field(default=None, description="City for this forecast")
    temperature_celsius: float | None = Field(
        default=None, description="Current/average temperature in Celsius"
    )
    conditions: str | None = Field(
        default=None, description="Text description of weather conditions"
    )
    precipitation_mm: float | None = Field(
        default=None, description="Estimated precipitation in millimeters"
    )
    humidity_percent: float | None = Field(
        default=None, description="Humidity percentage"
    )
    wind_speed_ms: float | None = Field(
        default=None, description="Wind speed in meters/second"
    )
    source: str | None = Field(default=None, description="Weather data source")
    provenance: Provenance = Field(description="Data source information")


class TransitLeg(BaseModel):
    """Transit option between two locations."""

    mode: TransitMode = Field(description="Transportation mode")
    from_geo: Geo = Field(description="Origin coordinates")
    to_geo: Geo = Field(description="Destination coordinates")
    duration_seconds: int = Field(description="Travel duration in seconds")
    last_departure: time | None = Field(
        default=None, description="Last departure for public transit"
    )
    price_usd_cents: int | None = Field(
        default=None, description="Estimated price in USD cents"
    )
    route_name: str | None = Field(
        default=None, description="Transit line or route name"
    )
    neighborhoods: list[str] | None = Field(
        default=None, description="Neighborhoods or areas served"
    )
    provenance: Provenance = Field(description="Data source information")


class FxRate(BaseModel):
    """Foreign exchange rate."""

    rate: float = Field(description="Exchange rate value")
    as_of: date = Field(description="Date the rate is valid for")
    provenance: Provenance = Field(description="Data source information")
