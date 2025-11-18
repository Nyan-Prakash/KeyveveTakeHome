"""Tests for MCP weather integration."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from backend.app.adapters.mcp import MCPWeatherAdapter, MCPException
from backend.app.models.tool_results import WeatherDay


class MockDirectWeatherAdapter:
    """Mock direct weather adapter for testing."""
    
    async def get_weather(self, city: str, target_date: date | None = None) -> WeatherDay:
        return WeatherDay(
            date=target_date or date.today(),
            city=city,
            temperature_celsius=25.0,
            conditions="sunny",
            precipitation_mm=0.0,
            humidity_percent=60,
            wind_speed_ms=3.0,
            source="mock_fallback"
        )


@pytest.fixture
def mcp_adapter():
    """Create MCP weather adapter with mock fallback."""
    fallback = MockDirectWeatherAdapter()
    return MCPWeatherAdapter(
        mcp_endpoint="http://localhost:3001",
        fallback_adapter=fallback,
        timeout=2.0
    )


@pytest.mark.asyncio
async def test_mcp_weather_success(mcp_adapter):
    """Test successful MCP weather call."""
    mock_mcp_response = {
        "current": {
            "temperature_celsius": 22.5,
            "conditions": "cloudy",
            "humidity": 65,
            "wind_speed_ms": 2.5
        },
        "forecast": []
    }
    
    with patch.object(mcp_adapter, '_get_weather_mcp') as mock_mcp:
        mock_mcp.return_value = WeatherDay(
            date=date.today(),
            city="Paris",
            temperature_celsius=22.5,
            conditions="cloudy",
            precipitation_mm=0.0,
            humidity_percent=65,
            wind_speed_ms=2.5,
            source="mcp_weather"
        )
        
        with patch.object(mcp_adapter, '_is_mcp_available') as mock_available:
            mock_available.return_value = True
            
            result = await mcp_adapter.get_weather("Paris")
            
            assert result.city == "Paris"
            assert result.temperature_celsius == 22.5
            assert result.conditions == "cloudy"
            assert result.source == "mcp_weather"


@pytest.mark.asyncio
async def test_mcp_weather_fallback(mcp_adapter):
    """Test fallback when MCP fails."""
    with patch.object(mcp_adapter, '_is_mcp_available') as mock_available:
        mock_available.return_value = False
        
        result = await mcp_adapter.get_weather("London")
        
        assert result.city == "London"
        assert result.source == "mock_fallback"
        assert result.temperature_celsius == 25.0


@pytest.mark.asyncio
async def test_mcp_weather_exception_fallback(mcp_adapter):
    """Test fallback when MCP throws exception."""
    with patch.object(mcp_adapter, '_is_mcp_available') as mock_available:
        mock_available.return_value = True
        
        with patch.object(mcp_adapter, '_get_weather_mcp') as mock_mcp:
            mock_mcp.side_effect = MCPException("MCP server error")
            
            result = await mcp_adapter.get_weather("Tokyo")
            
            assert result.city == "Tokyo"
            assert result.source == "mock_fallback"


@pytest.mark.asyncio
async def test_mcp_availability_check(mcp_adapter):
    """Test MCP availability checking and caching."""
    with patch('backend.app.adapters.mcp.weather.MCPClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # First call should check availability
        available = await mcp_adapter._is_mcp_available()
        assert available is True
        
        # Second call should use cached result
        available2 = await mcp_adapter._is_mcp_available()
        assert available2 is True
        
        # Health check should only be called once (cached)
        mock_client.health_check.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_parse_response():
    """Test MCP response parsing."""
    adapter = MCPWeatherAdapter("http://test", MockDirectWeatherAdapter())
    
    mcp_response = {
        "current": {
            "temperature_celsius": 18.5,
            "conditions": "rain",
            "humidity": 80,
            "wind_speed_ms": 4.2
        },
        "forecast": [
            {
                "date": "2025-11-18",
                "high_celsius": 20.0,
                "conditions": "cloudy",
                "precipitation_mm": 2.5
            }
        ]
    }
    
    result = adapter._parse_mcp_response(mcp_response, "Madrid", date(2025, 11, 18))
    
    assert result.city == "Madrid"
    assert result.temperature_celsius == 18.5
    assert result.conditions == "rain"
    assert result.humidity_percent == 80
    assert result.wind_speed_ms == 4.2
    assert result.source == "mcp_weather"


@pytest.mark.asyncio
async def test_mcp_parse_response_forecast_only():
    """Test MCP response parsing with only forecast data."""
    adapter = MCPWeatherAdapter("http://test", MockDirectWeatherAdapter())
    
    mcp_response = {
        "current": {},
        "forecast": [
            {
                "date": "2025-11-18",
                "high_celsius": 15.0,
                "conditions": "snow",
                "precipitation_mm": 8.0
            }
        ]
    }
    
    result = adapter._parse_mcp_response(mcp_response, "Helsinki", date(2025, 11, 18))
    
    assert result.city == "Helsinki"
    assert result.temperature_celsius == 15.0
    assert result.conditions == "snow"
    assert result.precipitation_mm == 8.0
    assert result.source == "mcp_weather"


def test_mcp_parse_response_invalid():
    """Test MCP response parsing with invalid data."""
    adapter = MCPWeatherAdapter("http://test", MockDirectWeatherAdapter())
    
    invalid_response = {"invalid": "data"}
    
    with pytest.raises(MCPException, match="Invalid MCP weather response format"):
        adapter._parse_mcp_response(invalid_response, "Test", date.today())
