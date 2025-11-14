"""
Feature mapper: pure functions to extract ChoiceFeatures from tool results.

This module provides deterministic, pure functions that convert tool-specific
result objects into the canonical ChoiceFeatures format used by the selector.

Per SPEC.md and roadmap PR5:
- All mapping functions are pure (no I/O, no side effects)
- Deterministic given the same input
- No selector/planner code should access raw tool fields directly
- Only ChoiceFeatures fields are used for scoring and selection
"""

from __future__ import annotations

from backend.app.models.plan import ChoiceFeatures
from backend.app.models.tool_results import (
    Attraction,
    FlightOption,
    FxRate,
    Lodging,
    TransitLeg,
    WeatherDay,
)


def map_flight_to_features(flight: FlightOption) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from a FlightOption.

    Args:
        flight: Flight option with pricing and timing

    Returns:
        ChoiceFeatures with cost and travel time populated
    """
    return ChoiceFeatures(
        cost_usd_cents=flight.price_usd_cents,
        travel_seconds=flight.duration_seconds,
        indoor=None,  # Not applicable to flights
        themes=None,  # Not applicable to flights
    )


def map_lodging_to_features(lodging: Lodging) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from a Lodging.

    Note: Lodging cost is per-night. The caller must multiply by number
    of nights to get total cost for multi-night stays.

    Args:
        lodging: Lodging option with pricing and amenities

    Returns:
        ChoiceFeatures with per-night cost populated
    """
    return ChoiceFeatures(
        cost_usd_cents=lodging.price_per_night_usd_cents,
        travel_seconds=None,  # Not applicable to lodging
        indoor=True,  # Hotels are always indoor
        themes=None,  # Could extract from tier/amenities in future
    )


def map_attraction_to_features(
    attraction: Attraction, themes: list[str] | None = None
) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from an Attraction.

    Args:
        attraction: Attraction with venue details
        themes: Optional list of desired themes to check compatibility

    Returns:
        ChoiceFeatures with cost, indoor status, and themes populated
    """
    # Extract themes based on venue type and metadata
    # In a real implementation, this would come from attraction metadata
    # For now, derive basic themes from venue_type
    attraction_themes: list[str] = []
    venue_type = attraction.venue_type.lower()

    if "museum" in venue_type:
        attraction_themes.append("art")
        attraction_themes.append("culture")
    elif "park" in venue_type:
        attraction_themes.append("outdoor")
        attraction_themes.append("nature")
    elif "temple" in venue_type or "church" in venue_type:
        attraction_themes.append("culture")
        attraction_themes.append("architecture")

    return ChoiceFeatures(
        cost_usd_cents=attraction.est_price_usd_cents or 0,
        travel_seconds=None,  # Activity duration, not travel time
        indoor=attraction.indoor,  # Tri-state: True/False/None
        themes=attraction_themes if attraction_themes else None,
    )


def map_transit_to_features(transit: TransitLeg) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from a TransitLeg.

    Args:
        transit: Transit option with routing and timing

    Returns:
        ChoiceFeatures with travel time populated
    """
    # Transit cost estimation (in cents)
    # These are fixture estimates based on mode
    cost_by_mode = {
        "walk": 0,  # Free
        "metro": 200,  # $2
        "bus": 150,  # $1.50
        "taxi": 1500,  # $15 base estimate
    }

    mode_str = (
        str(transit.mode.value) if hasattr(transit.mode, "value") else str(transit.mode)
    )
    cost = cost_by_mode.get(mode_str, 0)

    return ChoiceFeatures(
        cost_usd_cents=cost,
        travel_seconds=transit.duration_seconds,
        indoor=None,  # Not applicable to transit
        themes=None,  # Not applicable to transit
    )


def map_weather_to_features(weather: WeatherDay) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from a WeatherDay.

    Weather itself isn't a choice, but this helper exists for consistency.
    Weather data is typically used by verifiers, not as a selectable option.

    Args:
        weather: Weather forecast data

    Returns:
        ChoiceFeatures with all fields None/zero (weather is not a choice)
    """
    return ChoiceFeatures(
        cost_usd_cents=0,
        travel_seconds=None,
        indoor=None,
        themes=None,
    )


def map_fx_to_features(fx_rate: FxRate) -> ChoiceFeatures:
    """
    Extract ChoiceFeatures from an FxRate.

    FX rates aren't choices either, but included for API completeness.

    Args:
        fx_rate: Exchange rate data

    Returns:
        ChoiceFeatures with all fields None/zero (FX is not a choice)
    """
    return ChoiceFeatures(
        cost_usd_cents=0,
        travel_seconds=None,
        indoor=None,
        themes=None,
    )


# Type alias for convenience
ToolResult = FlightOption | Lodging | Attraction | TransitLeg | WeatherDay | FxRate


def map_tool_result_to_features(result: ToolResult) -> ChoiceFeatures:
    """
    Dispatch function to map any tool result to ChoiceFeatures.

    This is the primary entry point for feature extraction. It automatically
    dispatches to the appropriate type-specific mapper.

    Args:
        result: Any supported tool result type

    Returns:
        ChoiceFeatures extracted from the result

    Raises:
        TypeError: If result type is not recognized
    """
    if isinstance(result, FlightOption):
        return map_flight_to_features(result)
    elif isinstance(result, Lodging):
        return map_lodging_to_features(result)
    elif isinstance(result, Attraction):
        return map_attraction_to_features(result)
    elif isinstance(result, TransitLeg):
        return map_transit_to_features(result)
    elif isinstance(result, WeatherDay):
        return map_weather_to_features(result)
    elif isinstance(result, FxRate):
        return map_fx_to_features(result)
    else:
        raise TypeError(f"Unknown tool result type: {type(result).__name__}")
