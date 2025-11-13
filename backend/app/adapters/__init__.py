"""Adapter layer for external tools and fixture data sources."""

from backend.app.adapters.events import get_attractions
from backend.app.adapters.flights import get_flights
from backend.app.adapters.fx import get_fx_rate
from backend.app.adapters.lodging import get_lodging
from backend.app.adapters.transit import get_transit_leg
from backend.app.adapters.weather import get_weather_forecast

__all__ = [
    "get_weather_forecast",
    "get_flights",
    "get_lodging",
    "get_attractions",
    "get_transit_leg",
    "get_fx_rate",
]
