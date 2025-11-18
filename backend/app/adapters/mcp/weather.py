"""MCP Weather adapter with fallback to direct API calls."""

import logging
from datetime import date
from typing import Any

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

    def _parse_mcp_response(self, mcp_result: dict[str, Any], city: str, target_date: date | None) -> WeatherDay:
        """Parse MCP weather response into WeatherDay."""
        try:
            current = mcp_result.get("current", {})
            forecast = mcp_result.get("forecast", [])
            
            # Use current weather or first forecast day
            weather_data = current if current else (forecast[0] if forecast else {})
            
            return WeatherDay(
                date=target_date or date.today(),
                city=city,
                temperature_celsius=weather_data.get("temperature_celsius") or weather_data.get("high_celsius", 20.0),
                conditions=weather_data.get("conditions", "clear"),
                precipitation_mm=weather_data.get("precipitation_mm", 0.0),
                humidity_percent=weather_data.get("humidity", 50),
                wind_speed_ms=weather_data.get("wind_speed_ms", 0.0),
                source="mcp_weather"
            )
            
        except (KeyError, IndexError, TypeError) as e:
            raise MCPException(f"Invalid MCP weather response format: {e}")

    async def reset_availability_cache(self):
        """Reset MCP availability cache (useful for testing)."""
        self._mcp_available = None
