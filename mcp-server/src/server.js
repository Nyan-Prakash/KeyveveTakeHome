import express from 'express';
import dotenv from 'dotenv';
import { WeatherTool } from './weather-tool.js';
import { MCPProtocol } from './mcp-protocol.js';

// Load environment variables from .env file
dotenv.config();
console.log('🔧 Environment loaded, API key present:', !!process.env.WEATHER_API_KEY);

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(express.json());

// Check for required environment variables
const apiKey = process.env.WEATHER_API_KEY;
if (!apiKey || apiKey === 'your_api_key_here') {
  console.warn('⚠️  No valid WEATHER_API_KEY found in environment variables');
  console.warn('📝 Please set WEATHER_API_KEY in .env file');
  console.warn('🔗 Get your free API key from: https://openweathermap.org/api');
}

// Initialize weather tool
const weatherTool = new WeatherTool(apiKey);

// Initialize MCP protocol handler
const mcpProtocol = new MCPProtocol();
mcpProtocol.registerTool('weather', weatherTool);

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'weather-mcp-server',
    version: '1.0.0'
  });
});

// MCP protocol endpoints
app.post('/mcp/tools/list', async (req, res) => {
  try {
    const tools = mcpProtocol.listTools();
    res.json({
      tools,
      _meta: {
        protocol: 'mcp',
        version: '1.0.0'
      }
    });
  } catch (error) {
    res.status(500).json({
      error: 'Failed to list tools',
      details: error.message
    });
  }
});

app.post('/mcp/tools/call', async (req, res) => {
  try {
    const { tool, arguments: args } = req.body;
    
    if (!tool || !args) {
      return res.status(400).json({
        error: 'Missing tool or arguments',
        required: ['tool', 'arguments']
      });
    }

    const result = await mcpProtocol.callTool(tool, args);
    res.json({
      result,
      _meta: {
        tool,
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    res.status(400).json({
      error: 'Tool call failed',
      details: error.message
    });
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('Server error:', error);
  res.status(500).json({
    error: 'Internal server error',
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`🌤️  Weather MCP Server listening on port ${PORT}`);
  console.log(`📍 Health check: http://localhost:${PORT}/health`);
  console.log(`🔧 Tools endpoint: http://localhost:${PORT}/mcp/tools/list`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('⚡ SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('⚡ SIGINT received, shutting down gracefully');
  process.exit(0);
});
