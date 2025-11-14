"""Canonical feature mapper: Tool objects → ChoiceFeatures.

This module is the ONLY place where raw tool objects are converted to ChoiceFeatures.
All functions are pure, deterministic, and have no side effects.

Contract:
- Input: Typed tool result (FlightOption, Lodging, Attraction, TransitLeg)
- Output: Choice with populated ChoiceFeatures and Provenance
- Properties: Pure, deterministic, no I/O, no randomness, no global state
"""

from __future__ import annotations

from backend.app.models.common import ChoiceKind
from backend.app.models.plan import Choice, ChoiceFeatures
from backend.app.models.tool_results import (
    Attraction,
    FlightOption,
    Lodging,
    TransitLeg,
)


def flight_to_choice(flight: FlightOption) -> Choice:
    """
    Convert FlightOption to Choice with features.

    Args:
        flight: FlightOption with provenance

    Returns:
        Choice with ChoiceFeatures extracted from flight data
    """
    features = ChoiceFeatures(
        cost_usd_cents=flight.price_usd_cents,
        travel_seconds=flight.duration_seconds,
        indoor=None,  # Not applicable to flights
        themes=None,
    )

    return Choice(
        kind=ChoiceKind.flight,
        option_ref=flight.flight_id,
        features=features,
        score=None,  # Scoring happens in selector
        provenance=flight.provenance,
    )


def lodging_to_choice(lodging: Lodging, num_nights: int = 1) -> Choice:
    """
    Convert Lodging to Choice with features.

    Args:
        lodging: Lodging with provenance
        num_nights: Number of nights to calculate total cost

    Returns:
        Choice with ChoiceFeatures extracted from lodging data
    """
    # Total cost = price per night * number of nights
    total_cost = lodging.price_per_night_usd_cents * num_nights

    # Extract themes from tier
    themes = [lodging.tier.value]
    if lodging.kid_friendly:
        themes.append("kid_friendly")

    features = ChoiceFeatures(
        cost_usd_cents=total_cost,
        travel_seconds=None,  # Lodging doesn't involve travel
        indoor=True,  # Hotels/lodging are indoor
        themes=themes,
    )

    return Choice(
        kind=ChoiceKind.lodging,
        option_ref=lodging.lodging_id,
        features=features,
        score=None,
        provenance=lodging.provenance,
    )


def attraction_to_choice(attraction: Attraction) -> Choice:
    """
    Convert Attraction to Choice with features.

    Args:
        attraction: Attraction with provenance

    Returns:
        Choice with ChoiceFeatures extracted from attraction data
    """
    # Extract cost
    cost = attraction.est_price_usd_cents if attraction.est_price_usd_cents else 0

    # Extract themes from venue_type and other attributes
    themes = [attraction.venue_type]

    # Add kid_friendly theme if applicable
    if attraction.kid_friendly is True:
        themes.append("kid_friendly")

    # Map venue_type to additional themes
    venue_theme_map = {
        "museum": ["art", "culture", "education"],
        "park": ["nature", "outdoor", "relaxation"],
        "temple": ["culture", "spiritual", "historical"],
        "other": [],
    }
    themes.extend(venue_theme_map.get(attraction.venue_type, []))

    features = ChoiceFeatures(
        cost_usd_cents=cost,
        travel_seconds=None,  # Duration at attraction varies by visitor
        indoor=attraction.indoor,  # Tri-state: True/False/None
        themes=themes,
    )

    return Choice(
        kind=ChoiceKind.attraction,
        option_ref=attraction.id,
        features=features,
        score=None,
        provenance=attraction.provenance,
    )


def transit_to_choice(transit: TransitLeg) -> Choice:
    """
    Convert TransitLeg to Choice with features.

    Args:
        transit: TransitLeg with provenance

    Returns:
        Choice with ChoiceFeatures extracted from transit data
    """
    # Transit cost estimation (rough heuristics for fixtures)
    # Walk/Metro/Bus are cheap, Taxi is expensive
    cost_map = {
        "walk": 0,
        "metro": 300,  # ~$3 per trip
        "bus": 250,  # ~$2.50 per trip
        "taxi": 2000,  # ~$20 base fare
    }
    cost = cost_map.get(transit.mode.value, 500)

    # Themes based on mode
    themes = [transit.mode.value, "transport"]

    features = ChoiceFeatures(
        cost_usd_cents=cost,
        travel_seconds=transit.duration_seconds,
        indoor=None,  # Transit indoor/outdoor varies
        themes=themes,
    )

    return Choice(
        kind=ChoiceKind.transit,
        option_ref=f"{transit.mode.value}:{transit.from_geo.lat},{transit.from_geo.lon}-{transit.to_geo.lat},{transit.to_geo.lon}",
        features=features,
        score=None,
        provenance=transit.provenance,
    )


def to_choice(
    tool_obj: FlightOption | Lodging | Attraction | TransitLeg,
    **kwargs: int,  # For lodging num_nights
) -> Choice:
    """
    Universal converter: dispatch to appropriate mapper based on type.

    Args:
        tool_obj: Any typed tool result object
        **kwargs: Additional arguments (e.g., num_nights for lodging)

    Returns:
        Choice with ChoiceFeatures

    Raises:
        TypeError: If tool_obj type is not supported
    """
    if isinstance(tool_obj, FlightOption):
        return flight_to_choice(tool_obj)
    elif isinstance(tool_obj, Lodging):
        num_nights = kwargs.get("num_nights", 1)
        if not isinstance(num_nights, int):
            raise TypeError(f"num_nights must be int, got {type(num_nights)}")
        return lodging_to_choice(tool_obj, num_nights=num_nights)
    elif isinstance(tool_obj, Attraction):
        return attraction_to_choice(tool_obj)
    elif isinstance(tool_obj, TransitLeg):
        return transit_to_choice(tool_obj)
    else:
        raise TypeError(f"Unsupported tool object type: {type(tool_obj)}")
