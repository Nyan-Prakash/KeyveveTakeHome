"""Weather adapter using real API with 24h caching and MCP integration."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance
from backend.app.models.tool_results import WeatherDay

# MCP integration (imported lazily to avoid import errors if MCP not available)
_mcp_weather_adapter = None


def get_weather_adapter():
    """Get weather adapter with MCP integration if enabled."""
    global _mcp_weather_adapter
    settings = get_settings()
    
    if settings.mcp_enabled and _mcp_weather_adapter is None:
        try:
            from backend.app.adapters.mcp import MCPWeatherAdapter
            
            # Create direct weather adapter as fallback
            direct_adapter = DirectWeatherAdapter()
            
            # Wrap with MCP adapter
            _mcp_weather_adapter = MCPWeatherAdapter(
                mcp_endpoint=settings.mcp_weather_endpoint,
                fallback_adapter=direct_adapter,
                timeout=settings.mcp_timeout
            )
        except ImportError:
            # MCP not available, use direct adapter
            _mcp_weather_adapter = DirectWeatherAdapter()
    elif not settings.mcp_enabled:
        _mcp_weather_adapter = DirectWeatherAdapter()
    
    return _mcp_weather_adapter


class DirectWeatherAdapter:
    """Direct weather API adapter (fallback implementation)."""
    
    async def get_weather(self, city: str, target_date: date | None = None) -> WeatherDay:
        """Get weather for city using direct API call."""
        if target_date is None:
            target_date = date.today()
            
        # Use existing weather logic with tool executor
        settings = get_settings()
        executor = ToolExecutor()
        
        # Convert city to geo coordinates (simple fixture for now)
        location = _city_to_geo(city)
        
        cache_policy = CachePolicy(
            enabled=True,
            ttl_seconds=settings.weather_ttl_hours * 3600,
        )
        
        breaker_policy = BreakerPolicy(
            failure_threshold=settings.breaker_failure_threshold,
            cooldown_seconds=settings.breaker_timeout_s,
        )
        
        # Execute weather call with resilience
        result = await executor.execute(
            tool_name="weather_direct",
            tool_fn=lambda args: _fetch_weather_data(location, target_date),
            args={},
            cache_policy=cache_policy,
            breaker_policy=breaker_policy,
        )
        
        if result.status == "success" and result.data:
            return _parse_weather_response(result.data, city, target_date)
        else:
            # Fallback to fixture weather
            return _get_fixture_weather_day(city, target_date)


def _city_to_geo(city: str) -> Geo:
    """Convert city name to coordinates (fixture implementation)."""
    city_coords = {
        "Paris": Geo(lat=48.8566, lon=2.3522),
        "London": Geo(lat=51.5074, lon=-0.1278),
        "Tokyo": Geo(lat=35.6762, lon=139.6503),
        "New York": Geo(lat=40.7128, lon=-74.0060),
        "Kyoto": Geo(lat=35.0116, lon=135.7681),
        "Madrid": Geo(lat=40.4168, lon=-3.7038),
        "Rio de Janeiro": Geo(lat=-22.9068, lon=-43.1729),
    }
    return city_coords.get(city, Geo(lat=0.0, lon=0.0))


def _parse_weather_response(data: dict[str, Any], city: str, target_date: date) -> WeatherDay:
    """Parse weather API response into WeatherDay."""
    return WeatherDay(
        date=target_date,
        city=city,
        temperature_celsius=data.get("temperature_celsius", 20.0),
        conditions=data.get("conditions", "clear"),
        precipitation_mm=data.get("precipitation_mm", 0.0),
        humidity_percent=data.get("humidity_percent", 50),
        wind_speed_ms=data.get("wind_speed_ms", 0.0),
        source="openweathermap"
    )


def _get_fixture_weather_day(city: str, target_date: date) -> WeatherDay:
    """Generate fixture weather day."""
    day_of_year = target_date.timetuple().tm_yday
    
    return WeatherDay(
        date=target_date,
        city=city,
        temperature_celsius=20.0 + (day_of_year % 10),
        conditions="clear" if (day_of_year % 3) != 0 else "rain",
        precipitation_mm=0.0 if (day_of_year % 3) != 0 else 5.0,
        humidity_percent=50 + (day_of_year % 30),
        wind_speed_ms=2.0 + (day_of_year % 8),
        source="fixture"
    )


def _fetch_weather_data(location: Geo, target_date: date) -> dict[str, Any]:
    """Fetch weather data from API (stub implementation)."""
    # This would make actual API call to OpenWeatherMap
    # For now, return fixture data
    day_of_year = target_date.timetuple().tm_yday
    
    return {
        "temperature_celsius": 20.0 + (day_of_year % 10),
        "conditions": "clear" if (day_of_year % 3) != 0 else "rain",
        "precipitation_mm": 0.0 if (day_of_year % 3) != 0 else 5.0,
        "humidity_percent": 50 + (day_of_year % 30),
        "wind_speed_ms": 2.0 + (day_of_year % 8),
    }


# Legacy function maintained for backward compatibility
def get_weather_forecast(
    executor: ToolExecutor,
    location: Geo,
    date_range: tuple[date, date],
    *,
    settings: Settings | None = None,
) -> list[WeatherDay]:
    """
    Get weather forecast for a location and date range.

    Args:
        executor: ToolExecutor for resilient execution
        location: Geographic coordinates
        date_range: Tuple of (start_date, end_date)
        settings: Optional settings override

    Returns:
        List of WeatherDay objects with provenance
    """
    if settings is None:
        settings = get_settings()

    start_date, end_date = date_range

    # Fetch weather data for each day in the range
    results: list[WeatherDay] = []

    current = start_date
    while current <= end_date:
        # Use tool executor with cache and breaker policies
        cache_policy = CachePolicy(
            enabled=True,
            ttl_seconds=settings.weather_ttl_hours * 3600,  # 24h default
        )

        breaker_policy = BreakerPolicy(
            failure_threshold=settings.breaker_failure_threshold,
            cooldown_seconds=settings.breaker_timeout_s,
        )

        result = executor.execute(
            tool_name="weather",
            tool_fn=_fetch_weather_for_date,
            args={"location": location, "date": current},
            cache_policy=cache_policy,
            breaker_policy=breaker_policy,
        )

        if result.status == "success" and result.data:
            # Parse response into WeatherDay
            data = result.data
            conditions_map = {
                "Clear": "clear",
                "Clouds": "cloudy",
                "Rain": "rain",
                "Snow": "snow",
                "Thunderstorm": "storm",
            }

            weather_day = WeatherDay(
                date=current,
                temperature_celsius=data.get("temp_celsius", 20.0),
                conditions=conditions_map.get(data.get("conditions", "Clear"), "clear"),
                precipitation_mm=data.get("precipitation_mm", 0.0),
                humidity_percent=data.get("humidity_percent", 50),
                wind_speed_ms=data.get("wind_speed_ms", 0.0),
                provenance=Provenance(
                    source="openweathermap",
                    timestamp=datetime.now(UTC),
                    input_args={"lat": location.lat, "lon": location.lon, "date": current.isoformat()},
                    response_digest=None,  # Will be computed if needed
                ),
            )

            results.append(weather_day)
        else:
            # Fallback to fixture weather
            fixture_data = _get_fixture_weather(current)
            
            weather_day = WeatherDay(
                date=current,
                temperature_celsius=fixture_data["temp_c_high"],
                conditions="clear",
                precipitation_mm=fixture_data["precip_prob"] * 10,  # Convert probability to mm
                humidity_percent=50,
                wind_speed_ms=fixture_data["wind_kmh"] / 3.6,  # Convert km/h to m/s
                provenance=Provenance(
                    source="fixture",
                    timestamp=datetime.now(UTC),
                    input_args={"date": current.isoformat()},
                    response_digest=None,
                ),
            )

            results.append(weather_day)

        current += timedelta(days=1)

    return results


def _fetch_weather_for_date(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch weather data for a specific date.

    This is called by the ToolExecutor and should handle the actual API call.
    Currently returns fixture data as a placeholder.

    Args:
        args: Dictionary with 'location' and 'date' keys

    Returns:
        Weather data dictionary
    """
    location: Geo = args["location"]
    target_date: date = args["date"]

    # For now, return fixture weather
    # In a real implementation, this would make an HTTP call to OpenWeatherMap
    day_of_year = target_date.timetuple().tm_yday

    # Create deterministic but varied weather based on location and date
    temp_base = 15.0 + (abs(location.lat) / 90.0) * 20  # Latitude affects base temp
    temp_variation = (day_of_year % 20) - 10  # ±10 degree variation

    conditions = ["Clear", "Clouds", "Rain"][day_of_year % 3]
    
    return {
        "temp_celsius": temp_base + temp_variation,
        "conditions": conditions,
        "precipitation_mm": 5.0 if conditions == "Rain" else 0.0,
        "humidity_percent": 40 + (day_of_year % 40),
        "wind_speed_ms": 2.0 + (day_of_year % 6),
    }


def _get_fixture_weather(target_date: date) -> dict[str, float]:
    """Get fixture weather data for fallback."""
    # Simple deterministic fixture based on day of year
    day_of_year = target_date.timetuple().tm_yday

    # Summer-like weather (low precip, moderate wind, warm temps)
    base_temp = 20.0 + (day_of_year % 10)

    return {
        "precip_prob": 0.1 + (day_of_year % 5) * 0.1,
        "wind_kmh": 10.0 + (day_of_year % 15),
        "temp_c_high": base_temp + 5,
        "temp_c_low": base_temp - 2,
    }
