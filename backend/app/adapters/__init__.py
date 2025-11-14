"""Adapters for external data sources.

All adapters:
- Return typed Pydantic models with provenance
- Use ToolExecutor for resilience (timeout, retry, breaker, cache)
- Emit metrics via MetricsClient
- Are org-agnostic (no DB access)
"""

from .events import get_events
from .flights import get_flights
from .fx import get_fx_rate
from .lodging import get_lodging
from .transit import get_transit_legs
from .weather import get_weather_forecast

__all__ = [
    "get_weather_forecast",
    "get_flights",
    "get_lodging",
    "get_events",
    "get_transit_legs",
    "get_fx_rate",
]
