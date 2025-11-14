"""Transit adapter using computed fixture data."""

from __future__ import annotations

import math
from datetime import UTC, datetime, time
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance, TransitMode
from backend.app.models.tool_results import TransitLeg


def _haversine_distance(geo1: Geo, geo2: Geo) -> float:
    """
    Calculate great-circle distance between two points in km.

    Args:
        geo1: First coordinate
        geo2: Second coordinate

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth radius in km

    lat1_rad = math.radians(geo1.lat)
    lat2_rad = math.radians(geo2.lat)
    delta_lat = math.radians(geo2.lat - geo1.lat)
    delta_lon = math.radians(geo2.lon - geo1.lon)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# Transit speeds (km/h)
_TRANSIT_SPEEDS = {
    TransitMode.walk: 5.0,
    TransitMode.metro: 30.0,
    TransitMode.bus: 20.0,
    TransitMode.taxi: 35.0,
}

# Last departure times for public transit
_LAST_DEPARTURES = {
    TransitMode.metro: time(23, 30),
    TransitMode.bus: time(22, 0),
}


def get_transit_legs(
    executor: ToolExecutor,
    from_geo: Geo,
    to_geo: Geo,
    modes: list[TransitMode] | None = None,
) -> list[TransitLeg]:
    """
    Get transit options between two points (computed from distance).

    Args:
        executor: ToolExecutor for consistency
        from_geo: Origin coordinates
        to_geo: Destination coordinates
        modes: Transit modes to consider (default: all)

    Returns:
        List of TransitLeg objects with provenance
    """
    if modes is None:
        modes = [TransitMode.walk, TransitMode.metro, TransitMode.bus, TransitMode.taxi]

    def _compute_transit(args: dict[str, Any]) -> dict[str, Any]:
        from_geo_dict = args["from_geo"]
        to_geo_dict = args["to_geo"]
        allowed_modes = args["modes"]

        from_point = Geo(**from_geo_dict)
        to_point = Geo(**to_geo_dict)

        # Compute distance
        distance_km = _haversine_distance(from_point, to_point)

        results = []
        for mode_str in allowed_modes:
            mode = TransitMode(mode_str)
            speed_kmh = _TRANSIT_SPEEDS[mode]

            # Duration: distance / speed
            duration_hours = distance_km / speed_kmh
            duration_seconds = int(duration_hours * 3600)

            # Last departure (for public transit only)
            last_dep = _LAST_DEPARTURES.get(mode)

            leg_id = f"fixture:transit:{from_point.lat:.4f},{from_point.lon:.4f}-{to_point.lat:.4f},{to_point.lon:.4f}-{mode.value}"

            results.append(
                {
                    "leg_id": leg_id,
                    "mode": mode.value,
                    "from_geo": from_geo_dict,
                    "to_geo": to_geo_dict,
                    "duration_seconds": duration_seconds,
                    "last_departure": last_dep.isoformat() if last_dep else None,
                }
            )

        return {"transit": results}

    result = executor.execute(
        tool=_compute_transit,
        name="transit",
        args={
            "from_geo": {"lat": from_geo.lat, "lon": from_geo.lon},
            "to_geo": {"lat": to_geo.lat, "lon": to_geo.lon},
            "modes": [m.value for m in modes],
        },
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(
            failure_threshold=5,
            window_seconds=60,
            cooldown_seconds=30,
        ),
    )

    if result.status != "success":
        raise RuntimeError(f"Transit fixture failed: {result.status} - {result.error}")

    # Parse results
    if result.data is None:
        raise RuntimeError("Transit fixture returned no data")

    transit_data = result.data.get("transit", [])
    transit_legs: list[TransitLeg] = []

    for leg_dict in transit_data:
        last_dep = None
        if leg_dict["last_departure"]:
            last_dep = time.fromisoformat(leg_dict["last_departure"])

        leg = TransitLeg(
            mode=TransitMode(leg_dict["mode"]),
            from_geo=Geo(**leg_dict["from_geo"]),
            to_geo=Geo(**leg_dict["to_geo"]),
            duration_seconds=leg_dict["duration_seconds"],
            last_departure=last_dep,
            provenance=Provenance(
                source="tool",
                ref_id=leg_dict["leg_id"],
                source_url="fixture://transit",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )
        transit_legs.append(leg)

    return transit_legs
