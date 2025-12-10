#!/bin/bash

# Production deployment script for Triply Travel Planner

set -e

echo "🚀 Deploying Triply Travel Planner..."

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo "❌ Error: .env file not found"
    echo "💡 Copy .env.example to .env and configure your environment variables"
    exit 1
fi

# Source environment variables
source .env

# Check required environment variables
required_vars=("POSTGRES_PASSWORD" "OPENAI_API_KEY" "WEATHER_API_KEY" "JWT_PRIVATE_KEY_PEM" "JWT_PUBLIC_KEY_PEM")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "❌ Error: $var is not set in .env file"
        echo "💡 Please configure all required environment variables"
        exit 1
    fi
done

echo "✅ Environment variables validated"

# Build services
echo "📦 Building services..."
docker-compose build --no-cache

# Start dependencies first
echo "🗃️  Starting dependencies (postgres, redis, mcp-weather)..."
docker-compose up -d postgres redis mcp-weather

# Wait for dependencies to be healthy
echo "⏳ Waiting for dependencies to be healthy..."
for service in postgres redis mcp-weather; do
    echo "  Waiting for $service..."
    while ! docker-compose ps $service | grep -q "healthy"; do
        if docker-compose ps $service | grep -q "unhealthy"; then
            echo "❌ $service is unhealthy"
            docker-compose logs $service
            exit 1
        fi
        sleep 5
    done
    echo "  ✅ $service is healthy"
done

# Run database migrations
echo "🔄 Running database migrations..."
docker-compose run --rm backend alembic upgrade head

# Seed database with initial data
echo "🌱 Seeding database..."
if [[ -f scripts/seed_fixtures.py ]]; then
    docker-compose run --rm backend python scripts/seed_fixtures.py
else
    echo "⚠️  Seed script not found, skipping initial data seeding"
fi

# Start application services
echo "🎯 Starting application services..."
docker-compose up -d backend frontend

# Wait for application to be healthy
echo "⏳ Waiting for application to be healthy..."
for service in backend frontend; do
    echo "  Waiting for $service..."
    timeout=60
    while ! docker-compose ps $service | grep -q "healthy" && [[ $timeout -gt 0 ]]; do
        if docker-compose ps $service | grep -q "unhealthy"; then
            echo "❌ $service is unhealthy"
            docker-compose logs $service
            exit 1
        fi
        sleep 5
        timeout=$((timeout-5))
    done
    
    if [[ $timeout -le 0 ]]; then
        echo "❌ $service failed to become healthy within 60 seconds"
        docker-compose logs $service
        exit 1
    fi
    
    echo "  ✅ $service is healthy"
done

# Deployment complete
echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📱 Service URLs:"
echo "  🌐 Frontend:    http://localhost:${FRONTEND_PORT:-8501}"
echo "  🔧 Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo "  📊 Health:      http://localhost:${BACKEND_PORT:-8000}/healthz"
echo "  🌤️  MCP Weather: http://localhost:${MCP_PORT:-3001}/health"
echo ""
echo "🔍 Useful commands:"
echo "  📋 View logs:      docker-compose logs -f [service]"
echo "  🔄 Restart:        docker-compose restart [service]"
echo "  ⏹️  Stop all:       docker-compose down"
echo "  🗑️  Clean up:      docker-compose down -v --remove-orphans"
echo ""
echo "🎯 Next steps:"
echo "  1. Test the health endpoint: curl http://localhost:${BACKEND_PORT:-8000}/healthz"
echo "  2. Open the frontend: http://localhost:${FRONTEND_PORT:-8501}"
echo "  3. Check the logs: docker-compose logs -f"
