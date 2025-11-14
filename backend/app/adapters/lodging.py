"""Lodging adapter using fixture data."""

from datetime import UTC, datetime, time
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance, Tier, TimeWindow
from backend.app.models.tool_results import Lodging


class LodgingTool:
    """Tool for fetching lodging data from fixtures."""

    def __call__(self, args: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """
        Get fixture lodging options for a city.
        
        Args:
            args: Dict with keys city, checkin_date, checkout_date
            
        Returns:
            Dictionary with 'lodging' key containing list of lodging option dictionaries
        """
        # For simplicity in PR5, return Paris lodging for any city
        # In production would use dates for availability filtering

        # Fixture data for Paris (primary demo city)
        paris_lodging = [
            {
                "lodging_id": "paris_hotel_1",
                "name": "Hotel de Crillon",
                "lat": 48.8656,
                "lon": 2.3212,
                "price_per_night_usd_cents": 45000,  # $450/night
                "tier": "luxury",
                "kid_friendly": True,
                "checkin_start": "15:00",
                "checkin_end": "23:00",
                "checkout_start": "07:00",
                "checkout_end": "11:00"
            },
            {
                "lodging_id": "paris_hotel_2",
                "name": "Hotel Malte Opera",
                "lat": 48.8718,
                "lon": 2.3392,
                "price_per_night_usd_cents": 18000,  # $180/night
                "tier": "mid",
                "kid_friendly": True,
                "checkin_start": "14:00",
                "checkin_end": "22:00",
                "checkout_start": "07:00",
                "checkout_end": "11:00"
            },
            {
                "lodging_id": "paris_hotel_3",
                "name": "Hotel Jeanne d'Arc",
                "lat": 48.8551,
                "lon": 2.3656,
                "price_per_night_usd_cents": 9500,  # $95/night
                "tier": "budget",
                "kid_friendly": False,
                "checkin_start": "15:00",
                "checkin_end": "21:00",
                "checkout_start": "08:00",
                "checkout_end": "10:00"
            },
            {
                "lodging_id": "paris_hotel_4",
                "name": "Grand Hotel du Palais Royal",
                "lat": 48.8648,
                "lon": 2.3371,
                "price_per_night_usd_cents": 52000,  # $520/night
                "tier": "luxury",
                "kid_friendly": True,
                "checkin_start": "15:00",
                "checkin_end": "23:59",
                "checkout_start": "06:00",
                "checkout_end": "12:00"
            },
            {
                "lodging_id": "paris_hotel_5",
                "name": "Hotel des Grands Boulevards",
                "lat": 48.8717,
                "lon": 2.3439,
                "price_per_night_usd_cents": 22000,  # $220/night
                "tier": "mid",
                "kid_friendly": False,
                "checkin_start": "14:00",
                "checkin_end": "23:00",
                "checkout_start": "07:00",
                "checkout_end": "11:00"
            }
        ]

        # For simplicity, return Paris data for any city
        # In production would have multiple cities
        return {"lodging": paris_lodging}


class LodgingAdapter:
    """
    Lodging adapter using fixture data.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor
        self._tool = LodgingTool()

    def search_lodging(
        self,
        city: str,
        checkin_date: datetime,
        checkout_date: datetime
    ) -> list[Lodging]:
        """
        Search for lodging in a city.
        
        Args:
            city: City name
            checkin_date: Check-in date  
            checkout_date: Check-out date
            
        Returns:
            List of available lodging options
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
            name="lodging",
            args={
                "city": city,
                "checkin_date": checkin_date.strftime("%Y-%m-%d"),
                "checkout_date": checkout_date.strftime("%Y-%m-%d")
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            return []

        return self._parse_lodging(
            result.data.get("lodging", []),
            city,
            result.from_cache
        )

    def _parse_lodging(
        self,
        fixture_data: list[dict[str, Any]],
        city: str,
        from_cache: bool
    ) -> list[Lodging]:
        """
        Parse fixture data into Lodging models.
        """
        lodging_options = []

        for lodging_data in fixture_data:
            # Parse time windows
            checkin_window = TimeWindow(
                start=time.fromisoformat(lodging_data["checkin_start"]),
                end=time.fromisoformat(lodging_data["checkin_end"])
            )

            checkout_window = TimeWindow(
                start=time.fromisoformat(lodging_data["checkout_start"]),
                end=time.fromisoformat(lodging_data["checkout_end"])
            )

            # Create location
            geo = Geo(
                lat=lodging_data["lat"],
                lon=lodging_data["lon"]
            )

            # Map tier string to enum
            tier = Tier(lodging_data["tier"])

            # Create provenance
            provenance = Provenance(
                source="fixture",
                ref_id=f"fixture:lodging:{city}-{lodging_data['lodging_id']}",
                source_url="fixture://lodging",
                fetched_at=datetime.now(UTC),
                cache_hit=from_cache
            )

            lodging = Lodging(
                lodging_id=lodging_data["lodging_id"],
                name=lodging_data["name"],
                geo=geo,
                checkin_window=checkin_window,
                checkout_window=checkout_window,
                price_per_night_usd_cents=lodging_data["price_per_night_usd_cents"],
                tier=tier,
                kid_friendly=lodging_data["kid_friendly"],
                provenance=provenance
            )

            lodging_options.append(lodging)

        return lodging_options
