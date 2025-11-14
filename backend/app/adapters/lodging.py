"""Lodging adapter using fixture data."""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any, cast

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance, Tier, TimeWindow
from backend.app.models.tool_results import Lodging

# Fixture data: lodging options by city
_LODGING_FIXTURES = {
    "london": [
        {
            "id": "LHR-BUDGET-1",
            "name": "Cozy Inn Central",
            "geo": {"lat": 51.5074, "lon": -0.1278},
            "tier": "budget",
            "price_per_night": 80,
            "kid_friendly": True,
        },
        {
            "id": "LHR-MID-1",
            "name": "Thames View Hotel",
            "geo": {"lat": 51.5085, "lon": -0.1257},
            "tier": "mid",
            "price_per_night": 150,
            "kid_friendly": True,
        },
        {
            "id": "LHR-LUXURY-1",
            "name": "Royal Palace Suites",
            "geo": {"lat": 51.5094, "lon": -0.1340},
            "tier": "luxury",
            "price_per_night": 350,
            "kid_friendly": False,
        },
    ],
    "paris": [
        {
            "id": "CDG-BUDGET-1",
            "name": "Montmartre Hostel",
            "geo": {"lat": 48.8566, "lon": 2.3522},
            "tier": "budget",
            "price_per_night": 70,
            "kid_friendly": False,
        },
        {
            "id": "CDG-MID-1",
            "name": "Eiffel Charm Hotel",
            "geo": {"lat": 48.8584, "lon": 2.2945},
            "tier": "mid",
            "price_per_night": 180,
            "kid_friendly": True,
        },
        {
            "id": "CDG-LUXURY-1",
            "name": "Le Grand Hotel",
            "geo": {"lat": 48.8698, "lon": 2.3288},
            "tier": "luxury",
            "price_per_night": 450,
            "kid_friendly": False,
        },
    ],
    "tokyo": [
        {
            "id": "NRT-BUDGET-1",
            "name": "Shibuya Capsule Inn",
            "geo": {"lat": 35.6762, "lon": 139.6503},
            "tier": "budget",
            "price_per_night": 60,
            "kid_friendly": False,
        },
        {
            "id": "NRT-MID-1",
            "name": "Shinjuku Business Hotel",
            "geo": {"lat": 35.6895, "lon": 139.6917},
            "tier": "mid",
            "price_per_night": 140,
            "kid_friendly": True,
        },
        {
            "id": "NRT-LUXURY-1",
            "name": "Imperial Palace Hotel",
            "geo": {"lat": 35.6852, "lon": 139.7528},
            "tier": "luxury",
            "price_per_night": 500,
            "kid_friendly": True,
        },
    ],
}


def get_lodging(
    executor: ToolExecutor,
    city: str,
    seed: int | None = None,
) -> list[Lodging]:
    """
    Get lodging options from fixtures.

    Args:
        executor: ToolExecutor for consistency
        city: City name (lowercase, e.g., "london", "paris", "tokyo")
        seed: Random seed for determinism (unused in fixtures)

    Returns:
        List of Lodging objects with provenance
    """

    def _fetch_lodging(args: dict[str, Any]) -> dict[str, Any]:
        city_key = args["city"].lower()
        fixtures = _LODGING_FIXTURES.get(city_key, [])

        results = []
        for fixture in fixtures:
            results.append(
                {
                    "lodging_id": fixture["id"],
                    "name": fixture["name"],
                    "geo": fixture["geo"],
                    "tier": fixture["tier"],
                    "price_per_night_usd_cents": cast(int, fixture["price_per_night"])
                    * 100,
                    "kid_friendly": fixture["kid_friendly"],
                }
            )

        return {"lodging": results}

    result = executor.execute(
        tool=_fetch_lodging,
        name="lodging",
        args={"city": city},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(
            failure_threshold=5,
            window_seconds=60,
            cooldown_seconds=30,
        ),
    )

    if result.status != "success":
        raise RuntimeError(f"Lodging fixture failed: {result.status} - {result.error}")

    # Parse results
    if result.data is None:
        raise RuntimeError("Lodging fixture returned no data")

    lodging_data = result.data.get("lodging", [])
    lodging_options: list[Lodging] = []

    # Standard check-in/check-out windows
    checkin_window = TimeWindow(start=time(14, 0), end=time(22, 0))
    checkout_window = TimeWindow(start=time(6, 0), end=time(11, 0))

    for lodge_dict in lodging_data:
        lodge = Lodging(
            lodging_id=lodge_dict["lodging_id"],
            name=lodge_dict["name"],
            geo=Geo(**lodge_dict["geo"]),
            checkin_window=checkin_window,
            checkout_window=checkout_window,
            price_per_night_usd_cents=lodge_dict["price_per_night_usd_cents"],
            tier=Tier(lodge_dict["tier"]),
            kid_friendly=lodge_dict["kid_friendly"],
            provenance=Provenance(
                source="tool",
                ref_id=lodge_dict["lodging_id"],
                source_url="fixture://lodging",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )
        lodging_options.append(lodge)

    return lodging_options
