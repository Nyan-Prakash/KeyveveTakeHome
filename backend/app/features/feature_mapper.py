"""Canonical feature mapper that converts tool objects to Choice with ChoiceFeatures.

This is the ONLY place where raw tool data becomes ChoiceFeatures.
All functions are pure and deterministic.
"""

from backend.app.adapters.fx import FxRate
from backend.app.models import Choice, ChoiceFeatures, ChoiceKind
from backend.app.models.tool_results import (
    Attraction,
    FlightOption,
    Lodging,
    TransitLeg,
)


def flight_to_choice(flight: FlightOption) -> Choice:
    """
    Convert FlightOption to Choice with ChoiceFeatures.
    
    Args:
        flight: Flight option from adapter
        
    Returns:
        Choice with extracted features and provenance
    """
    features = ChoiceFeatures(
        cost_usd_cents=flight.price_usd_cents,
        travel_seconds=flight.duration_seconds,
        indoor=None,  # Indoor doesn't apply to flights
        themes=["travel", "flight"]
    )

    return Choice(
        kind=ChoiceKind.flight,
        option_ref=flight.flight_id,
        features=features,
        score=None,  # Scoring happens in selector (PR6)
        provenance=flight.provenance
    )


def lodging_to_choice(lodging: Lodging) -> Choice:
    """
    Convert Lodging to Choice with ChoiceFeatures.
    
    Args:
        lodging: Lodging option from adapter
        
    Returns:
        Choice with extracted features and provenance
    """
    # For lodging, cost represents price per night
    # travel_seconds doesn't apply to lodging

    # Derive themes from tier and attributes
    themes = ["lodging", lodging.tier.value]
    if lodging.kid_friendly:
        themes.append("kid_friendly")

    features = ChoiceFeatures(
        cost_usd_cents=lodging.price_per_night_usd_cents,
        travel_seconds=None,  # Lodging doesn't have travel time
        indoor=True,  # Hotels are indoor by definition
        themes=themes
    )

    return Choice(
        kind=ChoiceKind.lodging,
        option_ref=lodging.lodging_id,
        features=features,
        score=None,
        provenance=lodging.provenance
    )


def attraction_to_choice(attraction: Attraction) -> Choice:
    """
    Convert Attraction to Choice with ChoiceFeatures.
    
    Args:
        attraction: Attraction from adapter
        
    Returns:
        Choice with extracted features and provenance
    """
    # Extract themes from venue_type and any embedded themes
    themes = [attraction.venue_type]

    # Add common theme mappings
    if attraction.venue_type == "museum":
        themes.extend(["art", "culture", "indoor"])
    elif attraction.venue_type == "monument":
        themes.extend(["history", "scenic"])
    elif attraction.venue_type == "church":
        themes.extend(["religion", "architecture"])
    elif attraction.venue_type == "palace":
        themes.extend(["history", "royal", "art"])
    elif attraction.venue_type == "tour":
        themes.extend(["guided", "walking"])
    elif attraction.venue_type == "neighborhood":
        themes.extend(["walking", "local"])

    # Add kid-friendly theme
    if attraction.kid_friendly:
        themes.append("kid_friendly")

    # Cost handling - use estimated price or default to 0 for free attractions
    cost = attraction.est_price_usd_cents or 0

    features = ChoiceFeatures(
        cost_usd_cents=cost,
        travel_seconds=None,  # Attractions don't have intrinsic travel time
        indoor=attraction.indoor,  # Use the tri-state value directly
        themes=themes
    )

    return Choice(
        kind=ChoiceKind.attraction,
        option_ref=attraction.id,
        features=features,
        score=None,
        provenance=attraction.provenance
    )


def transit_to_choice(transit: TransitLeg) -> Choice:
    """
    Convert TransitLeg to Choice with ChoiceFeatures.
    
    Args:
        transit: Transit leg from adapter
        
    Returns:
        Choice with extracted features and provenance
    """
    # For transit, the main cost is time rather than money
    # Set cost to 0 as transit costs are typically handled separately

    themes = ["transit", transit.mode.value]

    # Add specific themes based on mode
    if transit.mode.value in ["metro", "bus"]:
        themes.append("public_transport")
    elif transit.mode.value == "walk":
        themes.extend(["walking", "exercise"])
    elif transit.mode.value == "taxi":
        themes.append("private_transport")

    features = ChoiceFeatures(
        cost_usd_cents=0,  # Transit costs handled separately
        travel_seconds=transit.duration_seconds,
        indoor=None,  # Transit doesn't have indoor/outdoor classification
        themes=themes
    )

    return Choice(
        kind=ChoiceKind.transit,
        option_ref=f"{transit.mode.value}:{transit.from_geo.lat:.4f},{transit.from_geo.lon:.4f}-{transit.to_geo.lat:.4f},{transit.to_geo.lon:.4f}",
        features=features,
        score=None,
        provenance=transit.provenance
    )


def fx_to_choice(fx_rate: FxRate) -> Choice:
    """
    Convert FxRate to Choice with ChoiceFeatures.
    
    Note: FX rates don't typically become choices in slots,
    but this maintains the pattern for completeness.
    
    Args:
        fx_rate: FX rate from adapter
        
    Returns:
        Choice with extracted features and provenance
    """
    # FX rates are special - they represent conversion rates
    # Cost represents the rate (multiplied by 10000 to get integer cents-like precision)
    cost_representation = int(fx_rate.rate * 10000)

    themes = ["fx", "currency", fx_rate.from_currency.lower(), fx_rate.to_currency.lower()]

    features = ChoiceFeatures(
        cost_usd_cents=cost_representation,  # Rate as integer representation
        travel_seconds=None,  # FX doesn't involve travel
        indoor=None,  # FX doesn't have indoor/outdoor
        themes=themes
    )

    # Use a custom choice kind or map to existing - for now use 'meal' as placeholder
    # In full implementation might extend ChoiceKind enum
    return Choice(
        kind=ChoiceKind.meal,  # Placeholder - could extend enum for 'fx'
        option_ref=f"{fx_rate.from_currency}-{fx_rate.to_currency}",
        features=features,
        score=None,
        provenance=fx_rate.provenance
    )
