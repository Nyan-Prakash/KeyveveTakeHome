"""Adapters for external data sources."""

from .attractions import AttractionsAdapter
from .flights import FlightAdapter
from .fx import FxAdapter
from .lodging import LodgingAdapter
from .transit import TransitAdapter
from .weather import WeatherAdapter

__all__ = [
    "WeatherAdapter",
    "FlightAdapter",
    "LodgingAdapter",
    "AttractionsAdapter",
    "TransitAdapter",
    "FxAdapter",
]
