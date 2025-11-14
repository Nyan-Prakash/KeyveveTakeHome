"""Flights adapter using fixture data."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Provenance
from backend.app.models.tool_results import FlightOption

# Fixture data: common routes with realistic timings
_FLIGHT_FIXTURES = {
    ("SEA", "LHR"): [
        {
            "duration_h": 9.5,
            "price_usd": 850,
            "departure_offset_h": 0,
            "overnight": True,
        },
        {
            "duration_h": 10.0,
            "price_usd": 720,
            "departure_offset_h": 3,
            "overnight": True,
        },
        {
            "duration_h": 9.25,
            "price_usd": 1050,
            "departure_offset_h": 6,
            "overnight": False,
        },
    ],
    ("LHR", "SEA"): [
        {
            "duration_h": 10.5,
            "price_usd": 880,
            "departure_offset_h": 0,
            "overnight": False,
        },
        {
            "duration_h": 11.0,
            "price_usd": 750,
            "departure_offset_h": 4,
            "overnight": False,
        },
    ],
    ("JFK", "CDG"): [
        {
            "duration_h": 7.5,
            "price_usd": 650,
            "departure_offset_h": 0,
            "overnight": True,
        },
        {
            "duration_h": 7.25,
            "price_usd": 780,
            "departure_offset_h": 2,
            "overnight": True,
        },
        {
            "duration_h": 7.75,
            "price_usd": 920,
            "departure_offset_h": 5,
            "overnight": False,
        },
    ],
    ("CDG", "JFK"): [
        {
            "duration_h": 8.5,
            "price_usd": 670,
            "departure_offset_h": 0,
            "overnight": False,
        },
        {
            "duration_h": 8.25,
            "price_usd": 800,
            "departure_offset_h": 3,
            "overnight": False,
        },
    ],
    ("SFO", "NRT"): [
        {
            "duration_h": 11.0,
            "price_usd": 950,
            "departure_offset_h": 0,
            "overnight": True,
        },
        {
            "duration_h": 11.5,
            "price_usd": 820,
            "departure_offset_h": 2,
            "overnight": True,
        },
    ],
    ("NRT", "SFO"): [
        {
            "duration_h": 9.5,
            "price_usd": 980,
            "departure_offset_h": 0,
            "overnight": False,
        },
        {
            "duration_h": 10.0,
            "price_usd": 850,
            "departure_offset_h": 4,
            "overnight": False,
        },
    ],
}


def get_flights(
    executor: ToolExecutor,
    origin: str,
    destination: str,
    departure_date: date,
    seed: int | None = None,
) -> list[FlightOption]:
    """
    Get flight options from fixtures.

    Args:
        executor: ToolExecutor for consistency (even though fixture-based)
        origin: Origin IATA code (e.g., "SEA")
        destination: Destination IATA code (e.g., "LHR")
        departure_date: Desired departure date
        seed: Random seed for determinism (unused in fixtures but kept for API consistency)

    Returns:
        List of FlightOption objects with provenance
    """

    # Define tool callable for fixture data
    def _fetch_flights(args: dict[str, Any]) -> dict[str, Any]:
        orig = args["origin"]
        dest = args["destination"]
        dep_date_str = args["departure_date"]

        # Parse date string back to date object
        dep_date = date.fromisoformat(dep_date_str)

        route_key = (orig, dest)
        fixtures = _FLIGHT_FIXTURES.get(route_key, [])

        # Build flight options
        results = []
        for idx, fixture in enumerate(fixtures):
            duration_seconds = int(fixture["duration_h"] * 3600)
            price_usd_cents = fixture["price_usd"] * 100

            # Departure time: base date + offset
            departure_time = datetime.combine(
                dep_date, datetime.min.time(), tzinfo=UTC
            ) + timedelta(hours=fixture["departure_offset_h"])

            # Arrival time: departure + duration
            arrival_time = departure_time + timedelta(seconds=duration_seconds)

            results.append(
                {
                    "flight_id": f"fixture:flight:{orig}-{dest}-{dep_date.isoformat()}-{idx}",
                    "origin": orig,
                    "dest": dest,
                    "departure": departure_time.isoformat(),
                    "arrival": arrival_time.isoformat(),
                    "duration_seconds": duration_seconds,
                    "price_usd_cents": price_usd_cents,
                    "overnight": fixture["overnight"],
                }
            )

        return {"flights": results}

    # Execute through ToolExecutor (no cache for fixtures, but exercises breaker)
    result = executor.execute(
        tool=_fetch_flights,
        name="flights",
        args={
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date.isoformat(),  # Serialize date for cache key
        },
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(
            failure_threshold=5,
            window_seconds=60,
            cooldown_seconds=30,
        ),
    )

    if result.status != "success":
        raise RuntimeError(f"Flights fixture failed: {result.status} - {result.error}")

    # Parse results
    if result.data is None:
        raise RuntimeError("Flights fixture returned no data")

    flights_data = result.data.get("flights", [])
    flights: list[FlightOption] = []

    for flight_dict in flights_data:
        flight = FlightOption(
            flight_id=flight_dict["flight_id"],
            origin=flight_dict["origin"],
            dest=flight_dict["dest"],
            departure=datetime.fromisoformat(flight_dict["departure"]),
            arrival=datetime.fromisoformat(flight_dict["arrival"]),
            duration_seconds=flight_dict["duration_seconds"],
            price_usd_cents=flight_dict["price_usd_cents"],
            overnight=flight_dict["overnight"],
            provenance=Provenance(
                source="tool",
                ref_id=flight_dict["flight_id"],
                source_url="fixture://flights",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )
        flights.append(flight)

    return flights
