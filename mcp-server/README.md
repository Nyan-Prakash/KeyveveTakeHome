# Weather MCP Server

Model Context Protocol (MCP) server for weather data integration with Triply Travel Planner.

## Overview

This server provides weather data through the MCP protocol, allowing the main application to call weather tools with standardized interfaces and graceful fallback mechanisms.

## API Endpoints

### Health Check
```
GET /health
```

Returns server health status.

### List Tools
```
POST /mcp/tools/list
```

Returns available MCP tools:
```json
{
  "tools": [
    {
      "name": "weather",
      "description": "Get current weather and forecast for a city",
      "inputSchema": { ... },
      "outputSchema": { ... }
    }
  ]
}
```

### Call Tool
```
POST /mcp/tools/call
```

Execute a weather tool call:
```json
{
  "tool": "weather",
  "arguments": {
    "city": "Paris",
    "days": 1
  }
}
```

## Development

### Local Development
```bash
cd mcp-server
npm install
npm run dev
```

### Docker Development
```bash
docker build -t weather-mcp-server .
docker run -p 3001:3001 -e WEATHER_API_KEY=your_key weather-mcp-server
```

### Testing
```bash
# Health check
curl http://localhost:3001/health

# List tools
curl -X POST http://localhost:3001/mcp/tools/list

# Call weather tool
curl -X POST http://localhost:3001/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "weather", "arguments": {"city": "Paris", "days": 1}}'
```

## Environment Variables

- `WEATHER_API_KEY`: OpenWeatherMap API key
- `PORT`: Server port (default: 3001)

## Error Handling

The server provides detailed error responses with appropriate HTTP status codes:

- `400`: Bad request (missing arguments, validation errors)
- `500`: Internal server error (API failures, unexpected errors)

## Integration

This MCP server is designed to work with the Triply backend's MCP client adapter, which provides:

- Automatic fallback to direct API calls if MCP is unavailable
- Request timeout and retry logic
- Health check monitoring
- Error propagation and logging
