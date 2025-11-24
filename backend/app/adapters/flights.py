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
    tier_prefs: list[str] | None = None,
    budget_usd_cents: int | None = None,
    target_price_cents: int | None = None,
    price_range: tuple[int, int] | None = None,
) -> list[FlightOption]:
    """
    Get flight options from fixture data with continuous budget targeting.

    Args:
        origin: Origin airport IATA code
        dest: Destination city name or airport IATA code
        date_window: Tuple of (earliest_departure, latest_return)
        avoid_overnight: Whether to filter out overnight flights
        tier_prefs: [DEPRECATED] Preferred flight tiers (budget, mid, premium)
        budget_usd_cents: Total trip budget for tier selection
        target_price_cents: Target price per flight leg (continuous targeting)
        price_range: Tuple of (min_price, max_price) for filtering (continuous targeting)

    Returns:
        List of FlightOption objects with provenance (≤6 options)

    Note:
        If target_price_cents and price_range are provided, they take precedence over tier_prefs.
        This enables continuous budget targeting instead of discrete tier bands.
    """
    start_date, end_date = date_window

    # Map city names to primary airport codes for destination
    city_to_airport = {
        "Rio de Janeiro": "GIG",
        "Madrid": "MAD", 
        "Paris": "CDG",
        "Tokyo": "NRT",
        "London": "LHR",
        "New York": "JFK",
    }
    
    # If dest is a city name, convert to airport code
    dest_airport = city_to_airport.get(dest, dest)

    # CONTINUOUS TARGETING: Use price range if provided
    use_continuous_targeting = target_price_cents is not None and price_range is not None

    if use_continuous_targeting:
        # Use continuous price filtering (preferred method)
        min_price, max_price = price_range
    else:
        # DEPRECATED: Fall back to tier-based logic for backward compatibility
        if tier_prefs is None:
            if budget_usd_cents:
                trip_days = max((end_date - start_date).days, 1)
                budget_per_day = budget_usd_cents / trip_days
                if budget_per_day < 15000:  # Less than $150/day
                    tier_prefs = ["budget"]
                elif budget_per_day < 30000:  # Less than $300/day
                    tier_prefs = ["budget", "mid"]
                else:  # $300+ per day
                    tier_prefs = ["mid", "premium"]
            else:
                tier_prefs = ["budget", "mid", "premium"]
        min_price = None
        max_price = None

    # Generate fixture flights for the date range
    flights: list[FlightOption] = []

    # Create a few flight options for outbound (use start_date)
    # and a few for return (use end_date)

    # Outbound flights
    outbound_date = start_date
    flights.extend(
        _generate_fixture_flights(
            origin,
            dest_airport,
            outbound_date,
            avoid_overnight,
            tier_prefs if not use_continuous_targeting else None,
            min_price,
            max_price,
        )
    )

    # Return flights (if different date)
    if end_date != start_date:
        return_date = end_date
        flights.extend(
            _generate_fixture_flights(
                dest_airport,
                origin,
                return_date,
                avoid_overnight,
                tier_prefs if not use_continuous_targeting else None,
                min_price,
                max_price,
            )
        )

    # Sort by closeness to target price if using continuous targeting
    if use_continuous_targeting and target_price_cents is not None:
        flights.sort(key=lambda f: abs(f.price_usd_cents - target_price_cents))

    # Limit to 6 total options as per spec
    return flights[:6]


def _generate_fixture_flights(
    origin: str,
    dest: str,
    flight_date: date,
    avoid_overnight: bool,
    tier_prefs: list[str] | None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[FlightOption]:
    """
    Generate fixture flight options for a route and date.

    Supports both tier-based (deprecated) and continuous price filtering.
    """
    flights: list[FlightOption] = []

    # Define flight variations with airline names: (departure_hour, duration_hours, price_tier, airline, flight_number)
    all_variations = [
        (8, 8, "budget", "Spirit Airlines", "NK8201"),  # Morning budget
        (14, 9, "budget", "JetBlue", "B6890"),  # Afternoon budget
        (10, 7, "mid", "American Airlines", "AA1052"),  # Morning mid-tier
        (16, 8, "mid", "Delta", "DL485"),  # Afternoon mid-tier
        (12, 6, "premium", "United Polaris", "UA147"),  # Midday premium
        (18, 7, "premium", "LATAM Business", "LA8065"),  # Evening premium
    ]

    # CONTINUOUS TARGETING: Filter by price range if provided
    if min_price is not None and max_price is not None:
        # Price will be computed below, so we'll filter after creation
        variations = all_variations
    elif tier_prefs is not None:
        # DEPRECATED: Filter variations by preferred tiers
        variations = [v for v in all_variations if v[2] in tier_prefs]

        # If no matches, include at least budget options
        if not variations:
            variations = [(8, 8, "budget", "Spirit Airlines", "NK8201"), (14, 9, "budget", "JetBlue", "B6890")]
    else:
        # No filtering - include all
        variations = all_variations

    for idx, (dep_hour, duration_hours, tier, airline, flight_num) in enumerate(variations):
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

        # Price based on tier with realistic ranges
        base_price = 50000  # $500 base
        if tier == "budget":
            price = base_price + (idx * 2000)  # $500-510
        elif tier == "mid":
            price = int(base_price * 1.5) + (idx * 3000)  # $750-765  
        else:  # premium
            price = int(base_price * 2.5) + (idx * 5000)  # $1250-1275

        # Create flight object with airline info
        flight_id = f"{flight_num}_{flight_date.strftime('%Y%m%d')}"

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
                source="fixture",
                ref_id=f"fixture:flight:{origin}-{dest}-{flight_date.isoformat()}-{flight_num}",
                source_url="fixture://flights",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )

        # Add airline info to the flight (we can use the flight_id to store this info)
        flight.flight_id = f"{airline} {flight_num}"  # Override to show airline name
        
        # Compute and set response digest for deduplication
        flight_data = flight.model_dump(mode="json")
        flight.provenance.response_digest = compute_response_digest(flight_data)

        flights.append(flight)

    # CONTINUOUS TARGETING: Filter by price range after creation
    if min_price is not None and max_price is not None:
        flights = [f for f in flights if min_price <= f.price_usd_cents <= max_price]

    return flights
