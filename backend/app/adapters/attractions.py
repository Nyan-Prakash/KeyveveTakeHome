"""Attractions/events adapter using fixture data."""

from datetime import UTC, datetime, time
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance
from backend.app.models.tool_results import Attraction, Window


class AttractionsTool:
    """Tool for fetching attractions data from fixtures."""

    def __call__(self, args: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """
        Get fixture attraction options for a city.

        Args:
            args: Dict with keys city, themes (optional)

        Returns:
            Dictionary with 'attractions' key containing list of attraction dictionaries
        """
        # For simplicity in PR5, return Paris attractions for any city
        # In production would use city and themes for filtering

        # Fixture data for Paris attractions
        paris_attractions: list[dict[str, Any]] = [
            {
                "id": "louvre",
                "name": "Louvre Museum",
                "venue_type": "museum",
                "indoor": True,
                "kid_friendly": True,
                "lat": 48.8606,
                "lon": 2.3376,
                "est_price_usd_cents": 1800,  # $18
                "themes": ["art", "culture", "history"],
                "opening_hours": {
                    "0": [{"start": "09:00", "end": "18:00"}],  # Monday
                    "1": [{"start": "09:00", "end": "21:45"}],  # Tuesday
                    "2": [{"start": "09:00", "end": "18:00"}],  # Wednesday
                    "3": [{"start": "09:00", "end": "21:45"}],  # Thursday
                    "4": [{"start": "09:00", "end": "21:45"}],  # Friday
                    "5": [{"start": "09:00", "end": "18:00"}],  # Saturday
                    "6": [{"start": "09:00", "end": "18:00"}],  # Sunday
                }
            },
            {
                "id": "eiffel_tower",
                "name": "Eiffel Tower",
                "venue_type": "monument",
                "indoor": False,
                "kid_friendly": True,
                "lat": 48.8584,
                "lon": 2.2945,
                "est_price_usd_cents": 2900,  # $29 for elevator
                "themes": ["monument", "scenic", "photo"],
                "opening_hours": {
                    "0": [{"start": "09:30", "end": "23:45"}],
                    "1": [{"start": "09:30", "end": "23:45"}],
                    "2": [{"start": "09:30", "end": "23:45"}],
                    "3": [{"start": "09:30", "end": "23:45"}],
                    "4": [{"start": "09:30", "end": "00:45"}],
                    "5": [{"start": "09:30", "end": "00:45"}],
                    "6": [{"start": "09:30", "end": "23:45"}],
                }
            },
            {
                "id": "notre_dame",
                "name": "Notre-Dame Cathedral",
                "venue_type": "church",
                "indoor": True,
                "kid_friendly": True,
                "lat": 48.8530,
                "lon": 2.3499,
                "est_price_usd_cents": 0,  # Free entry to cathedral area
                "themes": ["religion", "history", "architecture"],
                "opening_hours": {
                    "0": [{"start": "08:00", "end": "18:45"}],
                    "1": [{"start": "08:00", "end": "18:45"}],
                    "2": [{"start": "08:00", "end": "18:45"}],
                    "3": [{"start": "08:00", "end": "18:45"}],
                    "4": [{"start": "08:00", "end": "18:45"}],
                    "5": [{"start": "08:00", "end": "18:45"}],
                    "6": [{"start": "08:00", "end": "18:45"}],
                }
            },
            {
                "id": "versailles",
                "name": "Palace of Versailles",
                "venue_type": "palace",
                "indoor": None,  # Mixed indoor/outdoor
                "kid_friendly": True,
                "lat": 48.8049,
                "lon": 2.1204,
                "est_price_usd_cents": 2000,  # $20
                "themes": ["history", "royal", "gardens", "art"],
                "opening_hours": {
                    "0": [],  # Closed Monday
                    "1": [{"start": "09:00", "end": "18:30"}],
                    "2": [{"start": "09:00", "end": "18:30"}],
                    "3": [{"start": "09:00", "end": "18:30"}],
                    "4": [{"start": "09:00", "end": "18:30"}],
                    "5": [{"start": "09:00", "end": "18:30"}],
                    "6": [{"start": "09:00", "end": "18:30"}],
                }
            },
            {
                "id": "sacre_coeur",
                "name": "Basilica of Sacré-Cœur",
                "venue_type": "church",
                "indoor": True,
                "kid_friendly": True,
                "lat": 48.8867,
                "lon": 2.3431,
                "est_price_usd_cents": 0,  # Free entry
                "themes": ["religion", "scenic", "montmartre"],
                "opening_hours": {
                    "0": [{"start": "06:00", "end": "22:30"}],
                    "1": [{"start": "06:00", "end": "22:30"}],
                    "2": [{"start": "06:00", "end": "22:30"}],
                    "3": [{"start": "06:00", "end": "22:30"}],
                    "4": [{"start": "06:00", "end": "22:30"}],
                    "5": [{"start": "06:00", "end": "22:30"}],
                    "6": [{"start": "06:00", "end": "22:30"}],
                }
            },
            {
                "id": "musee_dorsay",
                "name": "Musée d'Orsay",
                "venue_type": "museum",
                "indoor": True,
                "kid_friendly": True,
                "lat": 48.8600,
                "lon": 2.3266,
                "est_price_usd_cents": 1600,  # $16
                "themes": ["art", "impressionist", "culture"],
                "opening_hours": {
                    "0": [],  # Closed Monday
                    "1": [{"start": "09:30", "end": "18:00"}],
                    "2": [{"start": "09:30", "end": "18:00"}],
                    "3": [{"start": "09:30", "end": "18:00"}],
                    "4": [{"start": "09:30", "end": "21:45"}],
                    "5": [{"start": "09:30", "end": "18:00"}],
                    "6": [{"start": "09:30", "end": "18:00"}],
                }
            },
            {
                "id": "montmartre_walk",
                "name": "Montmartre Walking Tour",
                "venue_type": "tour",
                "indoor": False,
                "kid_friendly": True,
                "lat": 48.8867,
                "lon": 2.3431,
                "est_price_usd_cents": 2500,  # $25 for guided tour
                "themes": ["walking", "scenic", "montmartre", "art"],
                "opening_hours": {
                    "0": [{"start": "10:00", "end": "17:00"}],
                    "1": [{"start": "10:00", "end": "17:00"}],
                    "2": [{"start": "10:00", "end": "17:00"}],
                    "3": [{"start": "10:00", "end": "17:00"}],
                    "4": [{"start": "10:00", "end": "17:00"}],
                    "5": [{"start": "10:00", "end": "17:00"}],
                    "6": [{"start": "10:00", "end": "17:00"}],
                }
            },
            {
                "id": "latin_quarter",
                "name": "Latin Quarter Exploration",
                "venue_type": "neighborhood",
                "indoor": False,
                "kid_friendly": True,
                "lat": 48.8518,
                "lon": 2.3428,
                "est_price_usd_cents": 0,  # Free exploration
                "themes": ["walking", "history", "food", "student"],
                "opening_hours": {
                    "0": [{"start": "08:00", "end": "23:00"}],
                    "1": [{"start": "08:00", "end": "23:00"}],
                    "2": [{"start": "08:00", "end": "23:00"}],
                    "3": [{"start": "08:00", "end": "23:00"}],
                    "4": [{"start": "08:00", "end": "23:00"}],
                    "5": [{"start": "08:00", "end": "23:00"}],
                    "6": [{"start": "08:00", "end": "23:00"}],
                }
            }
        ]

        # For simplicity, return Paris data for any city
        # In production would have multiple cities
        return {"attractions": paris_attractions}


class AttractionsAdapter:
    """
    Attractions adapter using fixture data.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor
        self._tool = AttractionsTool()

    def search_attractions(
        self,
        city: str,
        themes: list[str] | None = None
    ) -> list[Attraction]:
        """
        Search for attractions in a city.
        
        Args:
            city: City name
            themes: Optional list of themes to filter by
            
        Returns:
            List of available attractions
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
            name="attractions",
            args={
                "city": city,
                "themes": themes or []
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            return []

        return self._parse_attractions(
            result.data,
            city,
            result.from_cache
        )

    def _parse_attractions(
        self,
        fixture_data: dict[str, Any],
        city: str,
        from_cache: bool
    ) -> list[Attraction]:
        """
        Parse fixture data into Attraction models.
        """
        # Extract attractions list from the response
        attraction_list = fixture_data.get("attractions", [])

        attractions = []

        for attraction_data in attraction_list:
            # Parse opening hours
            opening_hours: dict[str, list[Window]] = {}
            for day_str, hours_list in attraction_data["opening_hours"].items():
                windows = []
                for hour_data in hours_list:
                    # For simplicity, use today's date with the times
                    # In production, would use proper timezone handling
                    today = datetime.now(UTC).date()
                    start_time = time.fromisoformat(hour_data["start"])
                    end_time = time.fromisoformat(hour_data["end"])

                    start_dt = datetime.combine(today, start_time, UTC)
                    end_dt = datetime.combine(today, end_time, UTC)

                    windows.append(Window(start=start_dt, end=end_dt))

                opening_hours[day_str] = windows

            # Create location
            geo = Geo(
                lat=attraction_data["lat"],
                lon=attraction_data["lon"]
            )

            # Create provenance
            provenance = Provenance(
                source="fixture",
                ref_id=f"fixture:attraction:{city}-{attraction_data['id']}",
                source_url="fixture://attractions",
                fetched_at=datetime.now(UTC),
                cache_hit=from_cache
            )

            attraction = Attraction(
                id=attraction_data["id"],
                name=attraction_data["name"],
                venue_type=attraction_data["venue_type"],
                indoor=attraction_data["indoor"],
                kid_friendly=attraction_data["kid_friendly"],
                opening_hours=opening_hours,
                location=geo,
                est_price_usd_cents=attraction_data["est_price_usd_cents"],
                provenance=provenance
            )

            attractions.append(attraction)

        return attractions
