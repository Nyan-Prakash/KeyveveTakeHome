"""Weather adapter with OpenWeatherMap API integration."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from backend.app.config import Settings, get_settings
from backend.app.exec.executor import ToolExecutor
from backend.app.exec.types import BreakerPolicy, CachePolicy
from backend.app.models.common import Geo, Provenance
from backend.app.models.tool_results import WeatherDay


class WeatherTool:
    """Tool for fetching weather data from OpenWeatherMap API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Fetch weather forecast for given coordinates.
        
        Args:
            args: Dict with keys lat, lon, days
            
        Returns:
            Weather forecast data
        """
        lat = args["lat"]
        lon = args["lon"]
        days = args["days"]

        # For simplicity in PR5, use current weather endpoint
        # In production, would use forecast endpoint for multi-day
        url = f"{self.base_url}/forecast"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "cnt": min(days * 8, 40)  # 8 forecasts per day (3-hour intervals)
        }

        with httpx.Client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


class WeatherAdapter:
    """
    Weather adapter with real OpenWeatherMap API and 24h caching.
    """

    def __init__(
        self,
        executor: ToolExecutor,
        settings: Settings | None = None
    ) -> None:
        self._executor = executor
        self._settings = settings or get_settings()
        self._tool = WeatherTool(self._settings.weather_api_key)

    def get_forecast(
        self,
        location: Geo,
        start_date: date,
        end_date: date
    ) -> list[WeatherDay]:
        """
        Get weather forecast for location and date range.
        
        Args:
            location: Geographic coordinates
            start_date: Start date for forecast
            end_date: End date for forecast (inclusive)
            
        Returns:
            List of weather forecasts, one per day
        """
        days = (end_date - start_date).days + 1
        if days > 5:
            # OpenWeatherMap free tier limits to 5 days
            days = 5

        # Cache policy: 24h TTL as specified
        cache_policy = CachePolicy(
            enabled=True,
            ttl_seconds=self._settings.weather_ttl_hours * 3600
        )

        # Breaker policy from settings
        breaker_policy = BreakerPolicy(
            failure_threshold=self._settings.breaker_failure_threshold,
            cooldown_seconds=self._settings.breaker_timeout_s
        )

        # Execute the tool call
        result = self._executor.execute(
            tool=self._tool,
            name="weather",
            args={
                "lat": location.lat,
                "lon": location.lon,
                "days": days
            },
            cache_policy=cache_policy,
            breaker_policy=breaker_policy
        )

        if result.status != "success" or result.data is None:
            # Return empty list for failures
            # In production, might want to return cached stale data or fixture fallback
            return []

        # Parse the API response
        return self._parse_forecast(result.data, location, start_date, result.from_cache)

    def _parse_forecast(
        self,
        api_data: dict[str, Any],
        location: Geo,
        start_date: date,
        from_cache: bool
    ) -> list[WeatherDay]:
        """
        Parse OpenWeatherMap API response into WeatherDay models.
        """
        forecast_list = api_data.get("list", [])

        # Group forecasts by date and take daily aggregates
        daily_data: dict[date, list[dict[str, Any]]] = {}

        for forecast in forecast_list:
            forecast_dt = datetime.fromtimestamp(forecast["dt"], UTC)
            forecast_date = forecast_dt.date()

            if forecast_date not in daily_data:
                daily_data[forecast_date] = []
            daily_data[forecast_date].append(forecast)

        # Convert to WeatherDay models
        weather_days = []
        current_date = start_date

        for i in range(len(daily_data)):
            if current_date in daily_data:
                day_forecasts = daily_data[current_date]

                # Aggregate the day's forecasts
                precip_probs = []
                wind_speeds = []
                temps_high = []
                temps_low = []

                for forecast in day_forecasts:
                    main = forecast["main"]
                    wind = forecast["wind"]

                    # Extract precipitation probability (0-1)
                    pop = forecast.get("pop", 0.0)  # Probability of precipitation
                    precip_probs.append(pop)

                    # Wind speed (convert from m/s to km/h)
                    wind_speed = wind.get("speed", 0) * 3.6
                    wind_speeds.append(wind_speed)

                    # Temperatures
                    temps_high.append(main["temp_max"])
                    temps_low.append(main["temp_min"])

                # Take maximums/averages as appropriate
                max_precip_prob = max(precip_probs) if precip_probs else 0.0
                max_wind_speed = max(wind_speeds) if wind_speeds else 0.0
                high_temp = max(temps_high) if temps_high else 0.0
                low_temp = min(temps_low) if temps_low else 0.0

                # Create provenance
                provenance = Provenance(
                    source="weather_api",
                    ref_id=f"weather:{location.lat:.4f},{location.lon:.4f}:{current_date.isoformat()}",
                    source_url=f"{self._tool.base_url}/forecast",
                    fetched_at=datetime.now(UTC),
                    cache_hit=from_cache
                )

                weather_day = WeatherDay(
                    forecast_date=current_date,
                    precip_prob=max_precip_prob,
                    wind_kmh=max_wind_speed,
                    temp_c_high=high_temp,
                    temp_c_low=low_temp,
                    provenance=provenance
                )

                weather_days.append(weather_day)

            current_date += timedelta(days=1)

        return weather_days
