"""Transit adapter using fixture data."""

from datetime import UTC, datetime, time
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance, TransitMode
from backend.app.models.tool_results import TransitLeg


class TransitTool:
    """Tool for fetching transit data from fixtures."""

    def __call__(self, args: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """
        Get fixture transit options between two points.
        
        Args:
            args: Dict with keys from_lat, from_lon, to_lat, to_lon
            
        Returns:
            Dictionary with 'transit' key containing list of transit option dictionaries
        """
        from_lat = args["from_lat"]
        from_lon = args["from_lon"]
        to_lat = args["to_lat"]
        to_lon = args["to_lon"]

        # Simple distance calculation for estimating durations
        # In production would use proper routing
        lat_diff = abs(to_lat - from_lat)
        lon_diff = abs(to_lon - from_lon)
        distance_estimate = ((lat_diff ** 2) + (lon_diff ** 2)) ** 0.5

        # Base fixture transit options for Paris area
        transit_options = [
            {
                "mode": "metro",
                "duration_base_minutes": 8,  # 8 minutes base + distance factor
                "duration_factor": 20,  # 20 minutes per degree
                "last_departure": "00:30"  # Metro runs until 12:30 AM
            },
            {
                "mode": "bus",
                "duration_base_minutes": 12,
                "duration_factor": 25,
                "last_departure": "23:30"  # Buses stop earlier
            },
            {
                "mode": "walk",
                "duration_base_minutes": 5,
                "duration_factor": 60,  # Walking is slower
                "last_departure": None  # Always available
            },
            {
                "mode": "taxi",
                "duration_base_minutes": 5,
                "duration_factor": 15,  # Faster in traffic
                "last_departure": None  # 24/7 service
            }
        ]

        # Calculate durations based on distance
        results = []
        for option in transit_options:
            duration_minutes = (
                option["duration_base_minutes"] +
                (distance_estimate * option["duration_factor"])
            )
            # Add some randomness but keep deterministic for same inputs
            hash_factor = hash(f"{from_lat}{from_lon}{to_lat}{to_lon}{option['mode']}") % 10
            duration_minutes += hash_factor  # 0-9 minute variation

            results.append({
                "mode": option["mode"],
                "duration_seconds": int(duration_minutes * 60),
                "last_departure": option["last_departure"]
            })

        return {"transit": results}


class TransitAdapter:
    """
    Transit adapter using fixture data with computed routes.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor
        self._tool = TransitTool()

    def get_transit_options(
        self,
        from_location: Geo,
        to_location: Geo
    ) -> list[TransitLeg]:
        """
        Get transit options between two locations.
        
        Args:
            from_location: Origin coordinates
            to_location: Destination coordinates
            
        Returns:
            List of transit options
        """
        cache_policy = CachePolicy(
            enabled=True,
            ttl_seconds=3600  # 1 hour for fixtures
        )

        breaker_policy = BreakerPolicy(
            failure_threshold=5,
            cooldown_seconds=60
        )

        # Execute the tool call
        result = self._executor.execute(
            tool=self._tool,
            name="transit",
            args={
                "from_lat": from_location.lat,
                "from_lon": from_location.lon,
                "to_lat": to_location.lat,
                "to_lon": to_location.lon
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            return []

        return self._parse_transit(
            result.data.get("transit", []),
            from_location,
            to_location,
            result.from_cache
        )

    def _parse_transit(
        self,
        fixture_data: list[dict[str, Any]],
        from_location: Geo,
        to_location: Geo,
        from_cache: bool
    ) -> list[TransitLeg]:
        """
        Parse fixture data into TransitLeg models.
        """
        transit_legs = []

        for transit_data in fixture_data:
            # Parse last departure time if available
            last_departure = None
            if transit_data["last_departure"]:
                last_departure = time.fromisoformat(transit_data["last_departure"])

            # Map mode string to enum
            mode = TransitMode(transit_data["mode"])

            # Create provenance
            provenance = Provenance(
                source="fixture",
                ref_id=f"fixture:transit:{mode.value}:{from_location.lat:.4f},{from_location.lon:.4f}-{to_location.lat:.4f},{to_location.lon:.4f}",
                source_url="fixture://transit",
                fetched_at=datetime.now(UTC),
                cache_hit=from_cache
            )

            transit_leg = TransitLeg(
                mode=mode,
                from_geo=from_location,
                to_geo=to_location,
                duration_seconds=transit_data["duration_seconds"],
                last_departure=last_departure,
                provenance=provenance
            )

            transit_legs.append(transit_leg)

        return transit_legs
