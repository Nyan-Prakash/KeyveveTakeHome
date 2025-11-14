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
    precip_prob: float = Field(description="Precipitation probability (0.0-1.0)")
    wind_kmh: float = Field(description="Wind speed in km/h")
    temp_c_high: float = Field(description="High temperature in Celsius")
    temp_c_low: float = Field(description="Low temperature in Celsius")
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
    provenance: Provenance = Field(description="Data source information")


class FxRate(BaseModel):
    """Foreign exchange rate."""

    from_currency: str = Field(description="Source currency code (ISO 4217)")
    to_currency: str = Field(description="Target currency code (ISO 4217)")
    rate: float = Field(description="Exchange rate (1 from_currency = rate to_currency)")
    as_of: date = Field(description="Date this rate is valid for")
    provenance: Provenance = Field(description="Data source information")
