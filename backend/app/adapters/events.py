"""Events/attractions adapter using fixture data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance
from backend.app.models.tool_results import Attraction, Window

# Fixture data: attractions by city
_EVENT_FIXTURES = {
    "london": [
        {
            "id": "LHR-MUSEUM-1",
            "name": "British Museum",
            "venue_type": "museum",
            "indoor": True,
            "kid_friendly": True,
            "geo": {"lat": 51.5194, "lon": -0.1270},
            "est_price_usd_cents": 0,  # Free entry
            "hours": {
                "0": [{"start": "10:00", "end": "17:30"}],  # Monday
                "1": [{"start": "10:00", "end": "17:30"}],
                "2": [{"start": "10:00", "end": "17:30"}],
                "3": [{"start": "10:00", "end": "17:30"}],
                "4": [{"start": "10:00", "end": "20:30"}],  # Friday - late
                "5": [{"start": "10:00", "end": "17:30"}],
                "6": [{"start": "10:00", "end": "17:30"}],
            },
        },
        {
            "id": "LHR-PARK-1",
            "name": "Hyde Park",
            "venue_type": "park",
            "indoor": False,
            "kid_friendly": True,
            "geo": {"lat": 51.5074, "lon": -0.1657},
            "est_price_usd_cents": 0,
            "hours": {
                "0": [{"start": "05:00", "end": "23:59"}],
                "1": [{"start": "05:00", "end": "23:59"}],
                "2": [{"start": "05:00", "end": "23:59"}],
                "3": [{"start": "05:00", "end": "23:59"}],
                "4": [{"start": "05:00", "end": "23:59"}],
                "5": [{"start": "05:00", "end": "23:59"}],
                "6": [{"start": "05:00", "end": "23:59"}],
            },
        },
        {
            "id": "LHR-TEMPLE-1",
            "name": "Westminster Abbey",
            "venue_type": "temple",
            "indoor": True,
            "kid_friendly": None,  # Unknown
            "geo": {"lat": 51.4993, "lon": -0.1273},
            "est_price_usd_cents": 2700,  # ~27 USD
            "hours": {
                "0": [{"start": "09:30", "end": "15:30"}],
                "1": [{"start": "09:30", "end": "15:30"}],
                "2": [{"start": "09:30", "end": "15:30"}],
                "3": [{"start": "09:30", "end": "15:30"}],
                "4": [{"start": "09:30", "end": "15:30"}],
                "5": [{"start": "09:00", "end": "15:00"}],
                "6": [],  # Closed Sunday
            },
        },
    ],
    "paris": [
        {
            "id": "CDG-MUSEUM-1",
            "name": "Louvre Museum",
            "venue_type": "museum",
            "indoor": True,
            "kid_friendly": True,
            "geo": {"lat": 48.8606, "lon": 2.3376},
            "est_price_usd_cents": 1700,  # ~17 EUR
            "hours": {
                "0": [{"start": "09:00", "end": "18:00"}],
                "1": [],  # Closed Tuesday
                "2": [{"start": "09:00", "end": "18:00"}],
                "3": [{"start": "09:00", "end": "21:45"}],  # Late Wednesday
                "4": [{"start": "09:00", "end": "18:00"}],
                "5": [{"start": "09:00", "end": "21:45"}],  # Late Friday
                "6": [{"start": "09:00", "end": "18:00"}],
            },
        },
        {
            "id": "CDG-PARK-1",
            "name": "Jardin du Luxembourg",
            "venue_type": "park",
            "indoor": False,
            "kid_friendly": True,
            "geo": {"lat": 48.8462, "lon": 2.3371},
            "est_price_usd_cents": 0,
            "hours": {
                "0": [{"start": "07:30", "end": "21:30"}],
                "1": [{"start": "07:30", "end": "21:30"}],
                "2": [{"start": "07:30", "end": "21:30"}],
                "3": [{"start": "07:30", "end": "21:30"}],
                "4": [{"start": "07:30", "end": "21:30"}],
                "5": [{"start": "07:30", "end": "21:30"}],
                "6": [{"start": "07:30", "end": "21:30"}],
            },
        },
        {
            "id": "CDG-OTHER-1",
            "name": "Eiffel Tower",
            "venue_type": "other",
            "indoor": None,  # Mixed - outdoor structure with indoor areas
            "kid_friendly": True,
            "geo": {"lat": 48.8584, "lon": 2.2945},
            "est_price_usd_cents": 2800,  # ~28 EUR for elevator to top
            "hours": {
                "0": [{"start": "09:30", "end": "23:45"}],
                "1": [{"start": "09:30", "end": "23:45"}],
                "2": [{"start": "09:30", "end": "23:45"}],
                "3": [{"start": "09:30", "end": "23:45"}],
                "4": [{"start": "09:30", "end": "23:45"}],
                "5": [{"start": "09:30", "end": "00:45"}],  # Late Friday
                "6": [{"start": "09:30", "end": "00:45"}],  # Late Saturday
            },
        },
    ],
    "tokyo": [
        {
            "id": "NRT-TEMPLE-1",
            "name": "Senso-ji Temple",
            "venue_type": "temple",
            "indoor": False,
            "kid_friendly": True,
            "geo": {"lat": 35.7148, "lon": 139.7967},
            "est_price_usd_cents": 0,
            "hours": {
                "0": [{"start": "06:00", "end": "17:00"}],
                "1": [{"start": "06:00", "end": "17:00"}],
                "2": [{"start": "06:00", "end": "17:00"}],
                "3": [{"start": "06:00", "end": "17:00"}],
                "4": [{"start": "06:00", "end": "17:00"}],
                "5": [{"start": "06:00", "end": "17:00"}],
                "6": [{"start": "06:00", "end": "17:00"}],
            },
        },
        {
            "id": "NRT-MUSEUM-1",
            "name": "Tokyo National Museum",
            "venue_type": "museum",
            "indoor": True,
            "kid_friendly": None,
            "geo": {"lat": 35.7188, "lon": 139.7764},
            "est_price_usd_cents": 600,  # ~600 JPY
            "hours": {
                "0": [],  # Closed Monday
                "1": [{"start": "09:30", "end": "17:00"}],
                "2": [{"start": "09:30", "end": "17:00"}],
                "3": [{"start": "09:30", "end": "17:00"}],
                "4": [{"start": "09:30", "end": "17:00"}],
                "5": [{"start": "09:30", "end": "21:00"}],  # Late Friday
                "6": [{"start": "09:30", "end": "17:00"}],
            },
        },
        {
            "id": "NRT-PARK-1",
            "name": "Yoyogi Park",
            "venue_type": "park",
            "indoor": False,
            "kid_friendly": True,
            "geo": {"lat": 35.6719, "lon": 139.6963},
            "est_price_usd_cents": 0,
            "hours": {
                "0": [{"start": "05:00", "end": "20:00"}],
                "1": [{"start": "05:00", "end": "20:00"}],
                "2": [{"start": "05:00", "end": "20:00"}],
                "3": [{"start": "05:00", "end": "20:00"}],
                "4": [{"start": "05:00", "end": "20:00"}],
                "5": [{"start": "05:00", "end": "20:00"}],
                "6": [{"start": "05:00", "end": "20:00"}],
            },
        },
    ],
}


def get_events(
    executor: ToolExecutor,
    city: str,
    seed: int | None = None,
) -> list[Attraction]:
    """
    Get attraction/event options from fixtures.

    Args:
        executor: ToolExecutor for consistency
        city: City name (lowercase, e.g., "london", "paris", "tokyo")
        seed: Random seed for determinism (unused in fixtures)

    Returns:
        List of Attraction objects with provenance
    """

    def _fetch_events(args: dict[str, Any]) -> dict[str, Any]:
        city_key = args["city"].lower()
        fixtures = _EVENT_FIXTURES.get(city_key, [])

        results: list[dict[str, Any]] = []
        for fixture in cast(list[dict[str, Any]], fixtures):
            results.append(fixture)

        return {"events": results}

    result = executor.execute(
        tool=_fetch_events,
        name="events",
        args={"city": city},
        cache_policy=CachePolicy(enabled=False),
        breaker_policy=BreakerPolicy(
            failure_threshold=5,
            window_seconds=60,
            cooldown_seconds=30,
        ),
    )

    if result.status != "success":
        raise RuntimeError(f"Events fixture failed: {result.status} - {result.error}")

    # Parse results
    if result.data is None:
        raise RuntimeError("Events fixture returned no data")

    events_data = result.data.get("events", [])
    attractions: list[Attraction] = []

    for event_dict in events_data:
        # Parse opening hours
        opening_hours: dict[str, list[Window]] = {}
        hours_dict: dict[str, list[dict[str, str]]] = event_dict["hours"]
        for weekday_str, hours_list in hours_dict.items():
            windows = []
            for hour_window in hours_list:
                # Parse time strings
                start_time = datetime.strptime(hour_window["start"], "%H:%M").time()
                end_time = datetime.strptime(hour_window["end"], "%H:%M").time()

                # Create timezone-aware datetime (use UTC for simplicity in fixtures)
                # In production, would use the city's actual timezone
                base_date = datetime.now(UTC).date()
                start_dt = datetime.combine(base_date, start_time, tzinfo=UTC)
                end_dt = datetime.combine(base_date, end_time, tzinfo=UTC)

                windows.append(Window(start=start_dt, end=end_dt))

            opening_hours[weekday_str] = windows

        attraction = Attraction(
            id=event_dict["id"],
            name=event_dict["name"],
            venue_type=event_dict["venue_type"],
            indoor=event_dict["indoor"],
            kid_friendly=event_dict["kid_friendly"],
            opening_hours=opening_hours,
            location=Geo(**event_dict["geo"]),
            est_price_usd_cents=event_dict["est_price_usd_cents"],
            provenance=Provenance(
                source="tool",
                ref_id=event_dict["id"],
                source_url="fixture://events",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            ),
        )
        attractions.append(attraction)

    return attractions
