"""Transit adapter using computed fixture data."""

import math
from datetime import UTC, datetime, time

from backend.app.models.common import (
    Geo,
    Provenance,
    TransitMode,
    compute_response_digest,
)
from backend.app.models.tool_results import TransitLeg


def get_transit_leg(
    from_geo: Geo,
    to_geo: Geo,
    mode_prefs: list[TransitMode] | None = None,
) -> TransitLeg:
    """
    Get transit option using computed haversine distance.

    Args:
        from_geo: Origin coordinates
        to_geo: Destination coordinates
        mode_prefs: Preferred transit modes

    Returns:
        TransitLeg object with computed duration and provenance
    """
    if mode_prefs is None or not mode_prefs:
        mode_prefs = [TransitMode.metro]

    # Use first preferred mode
    mode = mode_prefs[0]

    # Compute haversine distance
    distance_km = _haversine_distance(from_geo, to_geo)

    # Mode speeds (km/h) as per spec
    mode_speeds = {
        TransitMode.walk: 5,
        TransitMode.metro: 30,
        TransitMode.bus: 20,
        TransitMode.taxi: 25,
    }

    speed_kmh = mode_speeds.get(mode, 20)
    duration_hours = distance_km / speed_kmh
    duration_seconds = int(duration_hours * 3600)

    # Last departure for public transit
    last_departure: time | None = None
    if mode in (TransitMode.metro, TransitMode.bus):
        last_departure = time(23, 30)

    # Create transit leg
    # Round coords for stable ref_id
    from_key = f"{from_geo.lat:.2f},{from_geo.lon:.2f}"
    to_key = f"{to_geo.lat:.2f},{to_geo.lon:.2f}"

    leg = TransitLeg(
        mode=mode,
        from_geo=from_geo,
        to_geo=to_geo,
        duration_seconds=duration_seconds,
        last_departure=last_departure,
        provenance=Provenance(
            source="fixture",
            ref_id=f"fixture:transit:{from_key}-{to_key}-{mode.value}",
            source_url="fixture://transit",
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            response_digest=None,  # Computed below
        ),
    )

    # Compute and set response digest
    leg_data = leg.model_dump(mode="json")
    leg.provenance.response_digest = compute_response_digest(leg_data)

    return leg


def _haversine_distance(geo1: Geo, geo2: Geo) -> float:
    """
    Calculate haversine distance between two geographic points.

    Args:
        geo1: First coordinate
        geo2: Second coordinate

    Returns:
        Distance in kilometers
    """
    # Earth radius in km
    R = 6371.0

    # Convert to radians
    lat1 = math.radians(geo1.lat)
    lon1 = math.radians(geo1.lon)
    lat2 = math.radians(geo2.lat)
    lon2 = math.radians(geo2.lon)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance
