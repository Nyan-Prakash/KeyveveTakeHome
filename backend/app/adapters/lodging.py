"""Lodging adapter using fixture data."""

from datetime import UTC, date, datetime, time

from backend.app.models.common import (
    Geo,
    Provenance,
    Tier,
    TimeWindow,
    compute_response_digest,
)
from backend.app.models.tool_results import Lodging


def get_lodging(
    city: str,
    checkin: date,
    checkout: date,
    tier_prefs: list[Tier] | None = None,
    budget_usd_cents: int | None = None,
    rag_lodging_data: dict[int, dict] | None = None,
    target_price_cents: int | None = None,
    price_range: tuple[int, int] | None = None,
) -> list[Lodging]:
    """
    Get lodging options from RAG data with continuous budget targeting.

    Args:
        city: City name
        checkin: Check-in date
        checkout: Check-out date
        tier_prefs: [DEPRECATED] Preferred tiers (budget, mid, luxury)
        budget_usd_cents: Total trip budget for tier selection
        rag_lodging_data: Extracted lodging data from RAG chunks
        target_price_cents: Target price per night (continuous targeting)
        price_range: Tuple of (min_price, max_price) for filtering (continuous targeting)

    Returns:
        List of Lodging objects with provenance (≤4 options)

    Note:
        If target_price_cents and price_range are provided, they take precedence over tier_prefs.
        This enables continuous budget targeting instead of discrete tier bands.
    """
    # CONTINUOUS TARGETING: Use price range if provided
    use_continuous_targeting = target_price_cents is not None and price_range is not None

    if not use_continuous_targeting:
        # DEPRECATED: Determine tier preferences based on budget if not provided
        if tier_prefs is None:
            if budget_usd_cents:
                # Calculate trip duration and budget per night
                nights = max((checkout - checkin).days, 1)
                trip_days = max(nights, 1)
                budget_per_day = budget_usd_cents / trip_days

                if budget_per_day < 15000:  # Less than $150/day total budget
                    tier_prefs = [Tier.budget]  # Only budget lodging
                elif budget_per_day < 30000:  # Less than $300/day total budget
                    tier_prefs = [Tier.budget, Tier.mid]  # Budget + mid-tier
                elif budget_per_day < 60000:  # Less than $600/day total budget
                    tier_prefs = [Tier.mid, Tier.luxury]  # Mid + luxury tiers
                else:  # $600+ per day
                    tier_prefs = [Tier.luxury]  # Only luxury for very generous budgets
            else:
                tier_prefs = [Tier.budget, Tier.mid, Tier.luxury]

    # Generate lodging from RAG data if available, otherwise use fixtures
    if rag_lodging_data:
        all_lodging = _generate_rag_lodging(city, rag_lodging_data)
    else:
        all_lodging = _generate_fixture_lodging(city)

    # Filter by price range (continuous) or tier (deprecated)
    if use_continuous_targeting:
        min_price, max_price = price_range
        filtered = [
            option
            for option in all_lodging
            if min_price <= option.price_per_night_usd_cents <= max_price
        ]
        # Sort by closeness to target price
        filtered.sort(key=lambda l: abs(l.price_per_night_usd_cents - target_price_cents))
    else:
        # DEPRECATED: Filter by tier preferences
        filtered = [option for option in all_lodging if option.tier in tier_prefs]

    # Return up to 4 options
    return filtered[:4]


def _generate_rag_lodging(city: str, rag_data: dict[int, dict]) -> list[Lodging]:
    """Generate lodging options from RAG-extracted data.

    Args:
        city: City name for geo coordinates
        rag_data: Dictionary mapping index to lodging info with keys:
                  name, tier, amenities, neighborhood, price_per_night_usd_cents

    Returns:
        List of Lodging objects created from RAG data
    """
    lodging_options: list[Lodging] = []

    # Define city coordinates (could also extract from RAG in future)
    city_coords = {
        "Paris": Geo(lat=48.8566, lon=2.3522),
        "London": Geo(lat=51.5074, lon=-0.1278),
        "Tokyo": Geo(lat=35.6762, lon=139.6503),
        "New York": Geo(lat=40.7128, lon=-74.0060),
        "Munich": Geo(lat=48.1351, lon=11.5820),
        "Rio de Janeiro": Geo(lat=-22.9068, lon=-43.1729),
        "Madrid": Geo(lat=40.4168, lon=-3.7038),
    }

    base_geo = city_coords.get(city, Geo(lat=0.0, lon=0.0))

    for idx, lodging_info in rag_data.items():
        name = lodging_info.get("name", f"Unknown Lodging {idx}")
        tier_str = lodging_info.get("tier", "mid")
        price_cents = lodging_info.get("price_per_night_usd_cents", 15000)

        # Map tier string to Tier enum
        tier_map = {
            "budget": Tier.budget,
            "mid": Tier.mid,
            "mid-range": Tier.mid,
            "luxury": Tier.luxury,
            "boutique": Tier.luxury,  # Map boutique to luxury tier
        }
        tier = tier_map.get(tier_str.lower(), Tier.mid)

        # Determine kid_friendly from amenities or default to True for budget/mid
        amenities = lodging_info.get("amenities", [])
        kid_friendly = tier in [Tier.budget, Tier.mid]  # Budget/mid more likely kid-friendly

        # Slight geo variation for each lodging
        geo = Geo(lat=base_geo.lat + (idx * 0.01), lon=base_geo.lon + (idx * 0.01))

        lodging = Lodging(
            lodging_id=f"RAG{city.replace(' ', '')}{idx}",
            name=name,
            geo=geo,
            checkin_window=TimeWindow(start=time(15, 0), end=time(23, 0)),
            checkout_window=TimeWindow(start=time(7, 0), end=time(11, 0)),
            price_per_night_usd_cents=price_cents,
            tier=tier,
            kid_friendly=kid_friendly,
            provenance=Provenance(
                source="rag",
                ref_id=f"rag:lodge:{city}-{idx}",
                source_url="rag://lodging",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,  # Computed below
            ),
        )

        # Compute and set response digest
        lodging_data = lodging.model_dump(mode="json")
        lodging.provenance.response_digest = compute_response_digest(lodging_data)

        lodging_options.append(lodging)

    return lodging_options


def _generate_fixture_lodging(city: str) -> list[Lodging]:
    """Generate fixture lodging options for a city."""
    lodging_options: list[Lodging] = []

    # Define city coordinates (fixture)
    city_coords = {
        "Paris": Geo(lat=48.8566, lon=2.3522),
        "London": Geo(lat=51.5074, lon=-0.1278),
        "Tokyo": Geo(lat=35.6762, lon=139.6503),
        "New York": Geo(lat=40.7128, lon=-74.0060),
    }

    base_geo = city_coords.get(city, Geo(lat=0.0, lon=0.0))

    # Define lodging options by tier
    lodging_defs = [
        ("Budget Inn", Tier.budget, 8000, True),  # $80/night
        ("City Hostel", Tier.budget, 5000, True),
        ("Grand Hotel", Tier.mid, 15000, True),
        ("Plaza Suites", Tier.mid, 18000, True),
        ("Luxury Resort", Tier.luxury, 35000, False),
        ("Royal Palace Hotel", Tier.luxury, 42000, False),
    ]

    for idx, (name, tier, price, kid_friendly) in enumerate(lodging_defs):
        # Slight geo variation
        geo = Geo(lat=base_geo.lat + (idx * 0.01), lon=base_geo.lon + (idx * 0.01))

        lodging = Lodging(
            lodging_id=f"LODGE{city.replace(' ', '')}{idx}",
            name=name,
            geo=geo,
            checkin_window=TimeWindow(start=time(15, 0), end=time(23, 0)),
            checkout_window=TimeWindow(start=time(7, 0), end=time(11, 0)),
            price_per_night_usd_cents=price,
            tier=tier,
            kid_friendly=kid_friendly,
            provenance=Provenance(
                source="fixture",
                ref_id=f"fixture:lodge:{city}-{idx}",
                source_url="fixture://lodging",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,  # Computed below
            ),
        )

        # Compute and set response digest
        lodging_data = lodging.model_dump(mode="json")
        lodging.provenance.response_digest = compute_response_digest(lodging_data)

        lodging_options.append(lodging)

    return lodging_options
