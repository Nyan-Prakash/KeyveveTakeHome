import axios from 'axios';

/**
 * Weather tool that implements MCP tool interface
 */
export class WeatherTool {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseUrl = 'https://api.openweathermap.org/data/2.5';
    this.hasValidApiKey = apiKey && apiKey !== 'your_api_key_here';
  }

  /**
   * Get tool metadata for MCP protocol
   */
  getMetadata() {
    return {
      name: 'weather',
      description: 'Get current weather and forecast for a city',
      inputSchema: {
        type: 'object',
        properties: {
          city: {
            type: 'string',
            description: 'City name (e.g., "Paris", "Tokyo")'
          },
          days: {
            type: 'integer',
            description: 'Number of forecast days (1-5)',
            default: 1,
            minimum: 1,
            maximum: 5
          }
        },
        required: ['city']
      },
      outputSchema: {
        type: 'object',
        properties: {
          city: { type: 'string' },
          current: {
            type: 'object',
            properties: {
              temperature_celsius: { type: 'number' },
              conditions: { type: 'string' },
              humidity: { type: 'number' },
              wind_speed_ms: { type: 'number' }
            }
          },
          forecast: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                date: { type: 'string', format: 'date' },
                high_celsius: { type: 'number' },
                low_celsius: { type: 'number' },
                conditions: { type: 'string' },
                precipitation_mm: { type: 'number' }
              }
            }
          }
        }
      }
    };
  }

  /**
   * Execute weather tool call
   */
  async call(args) {
    const { city, days = 1 } = args;

    if (!city) {
      throw new Error('City parameter is required');
    }

    if (!this.hasValidApiKey) {
      return {
        error: 'Weather API not available',
        message: 'No valid OpenWeatherMap API key configured. Please set WEATHER_API_KEY in .env file.',
        help: 'Get your free API key from: https://openweathermap.org/api',
        city,
        mock_data: {
          city,
          current: {
            temperature_celsius: 20.0,
            conditions: 'clear',
            humidity: 65,
            wind_speed_ms: 3.5
          },
          forecast: days > 1 ? [{
            date: new Date().toISOString().split('T')[0],
            high_celsius: 25.0,
            low_celsius: 15.0,
            conditions: 'partly cloudy',
            precipitation_mm: 0.0
          }] : []
        }
      };
    }

    try {
      // Get current weather
      const currentWeather = await this._getCurrentWeather(city);
      
      // Get forecast if requested
      let forecast = [];
      if (days > 1) {
        forecast = await this._getForecast(city, days);
      }

      return {
        city,
        current: currentWeather,
        forecast,
        _meta: {
          source: 'openweathermap',
          timestamp: new Date().toISOString(),
          tool: 'weather'
        }
      };
    } catch (error) {
      throw new Error(`Weather API error: ${error.message}`);
    }
  }

  /**
   * Get current weather for city
   */
  async _getCurrentWeather(city) {
    const response = await axios.get(`${this.baseUrl}/weather`, {
      params: {
        q: city,
        appid: this.apiKey,
        units: 'metric'
      },
      timeout: 5000
    });

    const data = response.data;
    
    return {
      temperature_celsius: Math.round(data.main.temp * 10) / 10,
      conditions: data.weather[0].main.toLowerCase(),
      humidity: data.main.humidity,
      wind_speed_ms: Math.round(data.wind?.speed * 10) / 10 || 0
    };
  }

  /**
   * Get weather forecast for city
   */
  async _getForecast(city, days) {
    const response = await axios.get(`${this.baseUrl}/forecast`, {
      params: {
        q: city,
        appid: this.apiKey,
        units: 'metric',
        cnt: days * 8 // 8 forecasts per day (3-hour intervals)
      },
      timeout: 5000
    });

    const data = response.data;
    
    // Group forecasts by date
    const forecastByDate = {};
    
    data.list.forEach(item => {
      const date = item.dt_txt.split(' ')[0]; // Extract date part
      
      if (!forecastByDate[date]) {
        forecastByDate[date] = {
          temps: [],
          conditions: [],
          precipitation: 0
        };
      }
      
      forecastByDate[date].temps.push(item.main.temp);
      forecastByDate[date].conditions.push(item.weather[0].main.toLowerCase());
      
      if (item.rain) {
        forecastByDate[date].precipitation += item.rain['3h'] || 0;
      }
      if (item.snow) {
        forecastByDate[date].precipitation += item.snow['3h'] || 0;
      }
    });

    // Convert to forecast array
    return Object.entries(forecastByDate)
      .slice(0, days)
      .map(([date, data]) => ({
        date,
        high_celsius: Math.round(Math.max(...data.temps) * 10) / 10,
        low_celsius: Math.round(Math.min(...data.temps) * 10) / 10,
        conditions: this._getMostCommonCondition(data.conditions),
        precipitation_mm: Math.round(data.precipitation * 10) / 10
      }));
  }

  /**
   * Get most common weather condition from array
   */
  _getMostCommonCondition(conditions) {
    const counts = {};
    conditions.forEach(condition => {
      counts[condition] = (counts[condition] || 0) + 1;
    });
    
    return Object.entries(counts)
      .sort(([,a], [,b]) => b - a)[0][0];
  }
}
