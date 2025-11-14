"""Flight adapter using fixture data."""

from datetime import UTC, date, datetime, timedelta

from backend.app.models.common import (
    Provenance,
    compute_response_digest,
)
from backend.app.models.tool_results import FlightOption


def get_flights(
    origin: str,
    dest: str,
    date_window: tuple[date, date],
    avoid_overnight: bool = False,
) -> list[FlightOption]:
    """
    Get flight options from fixture data.

    Args:
        origin: Origin airport IATA code
        dest: Destination airport IATA code
        date_window: Tuple of (earliest_departure, latest_return)
        avoid_overnight: Whether to filter out overnight flights

    Returns:
        List of FlightOption objects with provenance (≤6 options)
    """
    start_date, end_date = date_window

    # Generate fixture flights for the date range
    flights: list[FlightOption] = []

    # Create a few flight options for outbound (use start_date)
    # and a few for return (use end_date)

    # Outbound flights
    outbound_date = start_date
    flights.extend(
        _generate_fixture_flights(origin, dest, outbound_date, avoid_overnight)
    )

    # Return flights (if different date)
    if end_date != start_date:
        return_date = end_date
        flights.extend(
            _generate_fixture_flights(dest, origin, return_date, avoid_overnight)
        )

    # Limit to 6 total options as per spec
    return flights[:6]


def _generate_fixture_flights(
    origin: str,
    dest: str,
    flight_date: date,
    avoid_overnight: bool,
) -> list[FlightOption]:
    """Generate fixture flight options for a route and date."""
    flights: list[FlightOption] = []

    # Define flight variations: (departure_hour, duration_hours, price_tier)
    variations = [
        (8, 8, "budget"),  # Morning budget
        (14, 9, "budget"),  # Afternoon budget
        (10, 7, "mid"),  # Morning mid-tier
        (16, 8, "mid"),  # Afternoon mid-tier
        (12, 6, "premium"),  # Midday premium
        (18, 7, "premium"),  # Evening premium
    ]

    for idx, (dep_hour, duration_hours, tier) in enumerate(variations):
        departure_time = datetime(
            flight_date.year,
            flight_date.month,
            flight_date.day,
            dep_hour,
            0,
            tzinfo=UTC,
        )
        arrival_time = departure_time + timedelta(hours=duration_hours)

        # Determine if overnight
        overnight = arrival_time.date() > departure_time.date()

        # Skip if avoiding overnight
        if avoid_overnight and overnight:
            continue

        # Price based on tier
        base_price = 50000  # $500
        if tier == "budget":
            price = base_price
        elif tier == "mid":
            price = int(base_price * 1.5)
        else:  # premium
            price = int(base_price * 2.5)

        # Create flight object
        flight_id = f"FL{origin}{dest}{flight_date.strftime('%Y%m%d')}{idx}"

        flight = FlightOption(
            flight_id=flight_id,
            origin=origin,
            dest=dest,
            departure=departure_time,
            arrival=arrival_time,
            duration_seconds=duration_hours * 3600,
            price_usd_cents=price,
            overnight=overnight,
            provenance=Provenance(
                source="fixture",  # Changed from "tool" to "fixture" for clarity
                ref_id=f"fixture:flight:{origin}-{dest}-{flight_date.isoformat()}-{idx}",
                source_url="fixture://flights",
                fetched_at=datetime.now(UTC),
                cache_hit=False,  # Will be overridden if called through executor cache
                response_digest=None,  # Computed below
            ),
        )

        # Compute and set response digest for deduplication
        flight_data = flight.model_dump(mode="json")
        flight.provenance.response_digest = compute_response_digest(flight_data)

        flights.append(flight)

    return flights
