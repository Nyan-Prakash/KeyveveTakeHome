"""Weather adapter using OpenWeatherMap API with 24h cache."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from backend.app.config import Settings
from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance
from backend.app.models.tool_results import WeatherDay


def get_weather_forecast(
    executor: ToolExecutor,
    settings: Settings,
    location: Geo,
    start_date: date,
    end_date: date,
) -> list[WeatherDay]:
    """
    Fetch weather forecast for a location and date range.

    Uses OpenWeatherMap OneCall API 3.0 with:
    - 24-hour cache (per location/date)
    - Circuit breaker protection
    - Timeout/retry via ToolExecutor

    Args:
        executor: ToolExecutor for resilience
        settings: App settings with weather_api_key
        location: Geographic coordinates
        start_date: First date to fetch
        end_date: Last date to fetch (inclusive)

    Returns:
        List of WeatherDay objects with provenance
    """

    # Define the tool callable for ToolExecutor
    async def _fetch_weather(args: dict[str, Any]) -> dict[str, Any]:
        lat = args["lat"]
        lon = args["lon"]
        api_key = args["api_key"]

        # OpenWeatherMap OneCall API 3.0
        # Note: For production, we'd use the real endpoint. For now, we use a simplified approach
        # that returns daily forecast data.
        url = "https://api.openweathermap.org/data/3.0/onecall"

        async with httpx.AsyncClient(timeout=settings.hard_timeout_s) as client:
            response = await client.get(
                url,
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": api_key,
                    "units": "metric",
                    "exclude": "current,minutely,hourly,alerts",
                },
            )
            response.raise_for_status()
            json_data: dict[str, Any] = response.json()
            return json_data

    # Execute with 24h cache + breaker
    result = executor.execute(
        tool=_fetch_weather,
        name="weather",
        args={
            "lat": location.lat,
            "lon": location.lon,
            "api_key": settings.weather_api_key,
        },
        cache_policy=CachePolicy(
            enabled=True,
            ttl_seconds=settings.weather_ttl_hours * 3600,
        ),
        breaker_policy=BreakerPolicy(
            failure_threshold=settings.breaker_failure_threshold,
            window_seconds=settings.breaker_timeout_s,
            cooldown_seconds=30,
        ),
    )

    # Handle errors
    if result.status == "breaker_open":
        error_dict = result.error or {}
        raise RuntimeError(
            f"Weather API breaker open, retry after {error_dict.get('retry_after_seconds', 30)}s"
        )
    if result.status != "success":
        raise RuntimeError(f"Weather API failed: {result.status} - {result.error}")

    # Parse response
    if result.data is None:
        raise RuntimeError("Weather API returned no data")

    data = result.data
    if not data or "daily" not in data:
        raise ValueError("Invalid weather API response: missing 'daily' field")

    daily_forecasts = data["daily"]

    # Map to WeatherDay objects
    weather_days: list[WeatherDay] = []
    current_date = start_date

    for day_data in daily_forecasts:
        if current_date > end_date:
            break

        # Extract fields from API response
        # OpenWeatherMap returns: temp, feels_like, pressure, humidity, dew_point,
        # wind_speed, wind_deg, weather, clouds, pop, rain, snow, uvi
        temp_data = day_data.get("temp", {})
        temp_high = temp_data.get("max", 20.0)
        temp_low = temp_data.get("min", 10.0)
        wind_speed_ms = day_data.get("wind_speed", 0.0)
        wind_kmh = wind_speed_ms * 3.6  # m/s to km/h
        precip_prob = day_data.get("pop", 0.0)  # probability of precipitation

        weather_day = WeatherDay(
            forecast_date=current_date,
            precip_prob=precip_prob,
            wind_kmh=wind_kmh,
            temp_c_high=temp_high,
            temp_c_low=temp_low,
            provenance=Provenance(
                source="tool",
                ref_id=f"weather:{location.lat:.4f},{location.lon:.4f}:{current_date.isoformat()}",
                source_url="https://api.openweathermap.org/data/3.0/onecall",
                fetched_at=datetime.now(UTC),
                cache_hit=result.from_cache,
                response_digest=None,  # Could add SHA256 of response if needed
            ),
        )
        weather_days.append(weather_day)
        current_date += timedelta(days=1)

    return weather_days
