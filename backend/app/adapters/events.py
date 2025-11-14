"""Events/Attractions adapter using fixture data."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from backend.app.models.common import Geo, Provenance, compute_response_digest
from backend.app.models.tool_results import Attraction, Window


def get_attractions(
    city: str,
    themes: list[str] | None = None,
    kid_friendly: bool = False,
) -> list[Attraction]:
    """
    Get attraction options from fixture data.

    Args:
        city: City name
        themes: Desired themes (art, food, outdoor, etc.)
        kid_friendly: Whether to filter for kid-friendly venues

    Returns:
        List of Attraction objects with provenance (≤20 matches)
    """
    if themes is None:
        themes = []

    # Generate all fixture attractions for the city
    all_attractions = _generate_fixture_attractions(city)

    # Filter by themes if specified
    if themes:
        filtered = [
            a
            for a in all_attractions
            if any(theme in a.name.lower() for theme in themes)
        ]
    else:
        filtered = all_attractions

    # Filter by kid_friendly if requested
    if kid_friendly:
        filtered = [a for a in filtered if a.kid_friendly is True]

    # Return up to 20 matches
    return filtered[:20]


def _generate_fixture_attractions(city: str) -> list[Attraction]:
    """Generate fixture attraction options for a city."""
    attractions: list[Attraction] = []

    # Define city coordinates and timezone
    city_data = {
        "Paris": {
            "geo": Geo(lat=48.8566, lon=2.3522),
            "tz": "Europe/Paris",
        },
        "London": {
            "geo": Geo(lat=51.5074, lon=-0.1278),
            "tz": "Europe/London",
        },
        "Tokyo": {
            "geo": Geo(lat=35.6762, lon=139.6503),
            "tz": "Asia/Tokyo",
        },
        "New York": {
            "geo": Geo(lat=40.7128, lon=-74.0060),
            "tz": "America/New_York",
        },
    }

    city_info = city_data.get(city, {"geo": Geo(lat=0.0, lon=0.0), "tz": "UTC"})
    base_geo = city_info["geo"]
    tz = ZoneInfo(city_info["tz"])

    # Define attraction templates
    # (name, venue_type, indoor, kid_friendly, price_cents, themes)
    attraction_defs = [
        ("Art Museum", "museum", True, True, 2000, ["art"]),
        ("National Gallery", "museum", True, True, 1500, ["art"]),
        ("Modern Art Center", "museum", True, False, 2500, ["art"]),
        ("City Park", "park", False, True, 0, ["outdoor"]),
        ("Botanical Garden", "park", False, True, 1000, ["outdoor"]),
        ("Historical Temple", "temple", None, True, 500, ["history"]),
        ("Cathedral", "temple", True, True, 0, ["history"]),
        ("Food Market", "other", False, True, 0, ["food"]),
        ("Fine Dining District", "other", None, False, 0, ["food"]),
        ("Aquarium", "other", True, True, 3000, ["kid"]),
        ("Zoo", "other", False, True, 2500, ["kid", "outdoor"]),
        ("Science Museum", "museum", True, True, 2000, ["kid", "education"]),
        ("Opera House", "other", True, False, 5000, ["culture"]),
        ("Theater District", "other", True, False, 4000, ["culture"]),
        ("Beach", "park", False, True, 0, ["outdoor"]),
        ("Shopping Mall", "other", True, True, 0, ["shopping"]),
        ("Historic District", "other", None, True, 0, ["history"]),
        ("Observation Deck", "other", True, True, 3500, ["sightseeing"]),
        ("Public Garden", "park", False, True, 0, ["outdoor"]),
        ("Concert Hall", "other", True, False, 6000, ["music"]),
    ]

    # Base time for creating opening hours
    base_date = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    for idx, (name, venue_type, indoor, kid_fr, price, _themes) in enumerate(
        attraction_defs
    ):
        # Create geo with slight variation
        geo = Geo(lat=base_geo.lat + (idx * 0.005), lon=base_geo.lon + (idx * 0.005))

        # Create opening hours (0=Monday, 6=Sunday)
        opening_hours: dict[str, list[Window]] = {}

        for day in range(7):
            if venue_type == "park" and day < 6:  # Parks open all day weekdays
                windows = [
                    Window(
                        start=base_date.replace(hour=6, minute=0),
                        end=base_date.replace(hour=22, minute=0),
                    )
                ]
            elif venue_type == "museum":
                if day == 0:  # Monday - some museums closed
                    windows = []
                else:
                    windows = [
                        Window(
                            start=base_date.replace(hour=10, minute=0),
                            end=base_date.replace(hour=18, minute=0),
                        )
                    ]
            elif venue_type == "temple":
                # Split hours
                windows = [
                    Window(
                        start=base_date.replace(hour=9, minute=0),
                        end=base_date.replace(hour=12, minute=0),
                    ),
                    Window(
                        start=base_date.replace(hour=14, minute=0),
                        end=base_date.replace(hour=18, minute=0),
                    ),
                ]
            else:  # other
                windows = [
                    Window(
                        start=base_date.replace(hour=10, minute=0),
                        end=base_date.replace(hour=20, minute=0),
                    )
                ]

            opening_hours[str(day)] = windows

        attraction = Attraction(
            id=f"ATTR{city.replace(' ', '')}{idx:03d}",
            name=name,
            venue_type=venue_type,
            indoor=indoor,
            kid_friendly=kid_fr,
            opening_hours=opening_hours,
            location=geo,
            est_price_usd_cents=price if price > 0 else None,
            provenance=Provenance(
                source="fixture",
                ref_id=f"fixture:attraction:{city}-{idx}",
                source_url="fixture://attractions",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,  # Computed below
            ),
        )

        # Compute and set response digest
        attraction_data = attraction.model_dump(mode="json")
        attraction.provenance.response_digest = compute_response_digest(attraction_data)

        attractions.append(attraction)

    return attractions
