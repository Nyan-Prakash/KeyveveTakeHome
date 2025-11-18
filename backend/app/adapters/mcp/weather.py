"""MCP Weather adapter with fallback to direct API calls."""

import logging
from datetime import UTC, date, datetime
from typing import Any

from backend.app.models.common import Provenance, compute_response_digest
from backend.app.models.tool_results import WeatherDay

from .client import MCPClient
from .exceptions import MCPException

logger = logging.getLogger(__name__)


class MCPWeatherAdapter:
    """Weather adapter that uses MCP with graceful fallback."""

    def __init__(self, mcp_endpoint: str, fallback_adapter, timeout: float = 3.0):
        """Initialize MCP weather adapter.
        
        Args:
            mcp_endpoint: MCP server endpoint (e.g., "http://localhost:3001")
            fallback_adapter: Fallback weather adapter to use if MCP fails
            timeout: MCP request timeout in seconds
        """
        self.mcp_endpoint = mcp_endpoint
        self.fallback_adapter = fallback_adapter
        self.timeout = timeout
        self._mcp_available: bool | None = None

    async def get_weather(self, city: str, target_date: date | None = None) -> WeatherDay:
        """Get weather for city with MCP + fallback.
        
        Args:
            city: City name
            target_date: Optional target date (defaults to today)
            
        Returns:
            WeatherDay object
        """
        # Try MCP first if available
        if await self._is_mcp_available():
            try:
                return await self._get_weather_mcp(city, target_date)
            except MCPException as e:
                logger.warning(f"MCP weather failed for {city}: {e}, falling back to direct API")
                self._mcp_available = False  # Mark as unavailable for subsequent calls

        # Fallback to direct API
        logger.debug(f"Using fallback weather adapter for {city}")
        return await self.fallback_adapter.get_weather(city, target_date)

    async def _is_mcp_available(self) -> bool:
        """Check if MCP server is available (cached)."""
        if self._mcp_available is None:
            try:
                async with MCPClient(self.mcp_endpoint, timeout=1.0) as client:
                    self._mcp_available = await client.health_check()
                    if self._mcp_available:
                        logger.info("MCP weather server is available")
                    else:
                        logger.warning("MCP weather server health check failed")
            except Exception as e:
                logger.warning(f"MCP weather server availability check failed: {e}")
                self._mcp_available = False

        return self._mcp_available

    async def _get_weather_mcp(self, city: str, target_date: date | None = None) -> WeatherDay:
        """Get weather via MCP server."""
        async with MCPClient(self.mcp_endpoint, timeout=self.timeout) as client:
            # Prepare arguments for MCP call
            args = {"city": city, "days": 1}
            
            # Call weather tool on MCP server
            result = await client.call_tool("weather", args)
            
            # Parse MCP response
            return self._parse_mcp_response(result, city, target_date)

    def _parse_mcp_response(
        self, mcp_result: dict[str, Any], city: str, target_date: date | None
    ) -> WeatherDay:
        """Parse MCP weather response into WeatherDay."""
        try:
            current = mcp_result.get("current", {}) or {}
            forecast = mcp_result.get("forecast", []) or []
            if not current and not forecast:
                raise MCPException("Invalid MCP weather response format: empty payload")
            target = target_date or date.today()

            selected_forecast = self._select_forecast_for_date(forecast, target)

            current_temp = current.get("temperature_celsius")
            temp_high = (
                selected_forecast.get("high_celsius")
                if selected_forecast
                else current_temp
            )
            temp_low = (
                selected_forecast.get("low_celsius")
                if selected_forecast
                else (current_temp - 3.0 if current_temp is not None else 15.0)
            )
            temperature = current_temp or temp_high or 20.0

            precip_mm = None
            if selected_forecast:
                precip_mm = selected_forecast.get("precipitation_mm")

            conditions = (
                (current.get("conditions") or "")
                or (selected_forecast.get("conditions") if selected_forecast else "")
            )

            precip_prob = self._estimate_precip_probability(
                precip_mm, conditions or ""
            )
            wind_speed_ms = current.get("wind_speed_ms", 0.0)
            wind_kmh = round(wind_speed_ms * 3.6, 1)

            provenance = Provenance(
                source="mcp_weather",
                ref_id=f"mcp_weather:{city}:{target.isoformat()}",
                source_url=f"{self.mcp_endpoint}/mcp/tools/call",
                fetched_at=datetime.now(UTC),
                cache_hit=False,
                response_digest=None,
            )

            weather = WeatherDay(
                forecast_date=target,
                precip_prob=precip_prob,
                wind_kmh=wind_kmh,
                temp_c_high=temp_high or temperature,
                temp_c_low=temp_low or temperature - 3.0,
                city=city,
                temperature_celsius=temperature,
                conditions=(conditions or "clear"),
                precipitation_mm=precip_mm,
                humidity_percent=current.get("humidity"),
                wind_speed_ms=wind_speed_ms,
                source="mcp_weather",
                provenance=provenance,
            )
            provenance.response_digest = compute_response_digest(
                {"current": current, "forecast": selected_forecast}
            )

            return weather

        except (KeyError, IndexError, TypeError) as e:
            raise MCPException(f"Invalid MCP weather response format: {e}") from e

    def _select_forecast_for_date(
        self, forecast: list[dict[str, Any]], target: date
    ) -> dict[str, Any] | None:
        """Select a forecast entry matching the desired date."""
        if not forecast:
            return None

        for entry in forecast:
            try:
                entry_date = entry.get("date")
                if entry_date and entry_date.startswith(target.isoformat()):
                    return entry
            except AttributeError:
                continue

        # Fallback to first entry
        return forecast[0]

    def _estimate_precip_probability(
        self, precip_mm: float | None, conditions: str
    ) -> float:
        """Estimate precipitation probability from MCP response data."""
        if precip_mm is None:
            precip_mm = 0.0

        prob = min(precip_mm / 10.0, 1.0)
        if conditions.lower() in {"rain", "snow", "storm"}:
            prob = max(prob, 0.7)
        return prob

    async def reset_availability_cache(self):
        """Reset MCP availability cache (useful for testing)."""
        self._mcp_available = None
