"""Flight adapter using fixture data."""

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Provenance
from backend.app.models.tool_results import FlightOption


class FlightTool:
    """Tool for fetching flight data from fixtures."""

    def __call__(self, args: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """
        Get fixture flight options.
        
        Args:
            args: Dict with keys origin, dest, date
            
        Returns:
            Dictionary with 'flights' key containing list of flight option dictionaries
        """
        origin = args["origin"]
        dest = args["dest"]
        # In production would use date for availability filtering

        # Fixture data for common routes
        fixture_flights = {
            ("SEA", "CDG"): [
                {
                    "flight_id": "AF8350",
                    "departure_offset_hours": 14,  # 2pm local
                    "duration_hours": 10.5,
                    "price_usd_cents": 65000,  # $650
                    "overnight": True
                },
                {
                    "flight_id": "LH490",
                    "departure_offset_hours": 17,  # 5pm local
                    "duration_hours": 11,
                    "price_usd_cents": 72000,  # $720
                    "overnight": True
                }
            ],
            ("CDG", "SEA"): [
                {
                    "flight_id": "AF8351",
                    "departure_offset_hours": 10,  # 10am local
                    "duration_hours": 11.5,
                    "price_usd_cents": 68000,  # $680
                    "overnight": False
                },
                {
                    "flight_id": "LH491",
                    "departure_offset_hours": 13,  # 1pm local
                    "duration_hours": 12,
                    "price_usd_cents": 75000,  # $750
                    "overnight": False
                }
            ],
            ("SEA", "ORY"): [
                {
                    "flight_id": "KL644",
                    "departure_offset_hours": 16,  # 4pm local
                    "duration_hours": 12,
                    "price_usd_cents": 59000,  # $590
                    "overnight": True
                }
            ],
            ("ORY", "SEA"): [
                {
                    "flight_id": "KL645",
                    "departure_offset_hours": 11,  # 11am local
                    "duration_hours": 12.5,
                    "price_usd_cents": 61000,  # $610
                    "overnight": False
                }
            ]
        }

        route_key = (origin, dest)
        flights = fixture_flights.get(route_key, [])
        return {"flights": flights}


class FlightAdapter:
    """
    Flight adapter using fixture data.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor
        self._tool = FlightTool()

    def search_flights(
        self,
        origin: str,
        dest: str,
        departure_date: datetime
    ) -> list[FlightOption]:
        """
        Search for flights between airports.
        
        Args:
            origin: Origin airport IATA code
            dest: Destination airport IATA code  
            departure_date: Desired departure date/time
            
        Returns:
            List of available flight options
        """
        # Use minimal caching since it's fixture data
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
            name="flights",
            args={
                "origin": origin,
                "dest": dest,
                "date": departure_date.strftime("%Y-%m-%d")
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            return []

        # Parse fixture data into FlightOption models
        return self._parse_flights(
            result.data.get("flights", []),
            origin,
            dest,
            departure_date,
            result.from_cache
        )

    def _parse_flights(
        self,
        fixture_data: list[dict[str, Any]],
        origin: str,
        dest: str,
        departure_date: datetime,
        from_cache: bool
    ) -> list[FlightOption]:
        """
        Parse fixture data into FlightOption models.
        """
        flight_options = []

        for flight_data in fixture_data:
            # Calculate actual departure/arrival times
            departure_dt = departure_date.replace(
                hour=flight_data["departure_offset_hours"],
                minute=0,
                second=0,
                microsecond=0
            )

            duration_seconds = int(flight_data["duration_hours"] * 3600)
            arrival_dt = departure_dt + timedelta(seconds=duration_seconds)

            # Create provenance
            provenance = Provenance(
                source="fixture",
                ref_id=f"fixture:flight:{origin}-{dest}-{flight_data['flight_id']}",
                source_url="fixture://flights",
                fetched_at=datetime.now(UTC),
                cache_hit=from_cache
            )

            flight_option = FlightOption(
                flight_id=flight_data["flight_id"],
                origin=origin,
                dest=dest,
                departure=departure_dt,
                arrival=arrival_dt,
                duration_seconds=duration_seconds,
                price_usd_cents=flight_data["price_usd_cents"],
                overnight=flight_data["overnight"],
                provenance=provenance
            )

            flight_options.append(flight_option)

        return flight_options
