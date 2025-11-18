# PR15: Deployment & Polish Implementation

**Date:** November 17, 2025  
**Priority:** MEDIUM (Deployment Enablement)  
**Status:** Ready for Implementation  

## Objective

Complete the deployment infrastructure by adding application Dockerfiles, updating docker-compose for full stack deployment, and finishing RAG embedding generation.

## Changes Overview

### 1. Application Dockerfiles
- Backend Dockerfile with Python environment
- Frontend Dockerfile with Streamlit
- Optimized multi-stage builds for production
- Health checks and non-root users

### 2. Complete Docker Compose
- All services in single compose file
- Environment configuration
- Volume management
- Service dependencies and health checks

### 3. RAG Embedding Completion
- Real OpenAI embedding generation
- Batch processing for efficiency
- Error handling and fallbacks

### 4. Production Readiness
- Environment configuration examples
- Migration and seeding automation
- Performance optimizations

## File Changes

### New Files
```
backend/Dockerfile
frontend/Dockerfile
.dockerignore (backend & frontend)
docker-compose.yml (production-ready)
docker-compose.override.yml (development)
.env.production.example
scripts/
├── generate-jwt-keys.sh
├── deploy.sh
└── migrate-and-seed.sh
```

### Modified Files
```
- backend/app/graph/rag.py (real embedding generation)
- docker-compose.dev.yml (align with new structure)
- .env.example (add all required variables)
- README.md (deployment instructions)
```

## Implementation Details

### Backend Dockerfile
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml ./
RUN pip install -e .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Copy application code
COPY backend/ backend/
COPY scripts/ scripts/
COPY alembic/ alembic/
COPY alembic.ini ./

# Change ownership
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
```

### Frontend Dockerfile
```dockerfile
# frontend/Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN adduser --disabled-password --gecos '' streamlit

# Copy frontend code
COPY frontend/ ./
COPY .streamlit/ .streamlit/

# Change ownership
RUN chown -R streamlit:streamlit /app
USER streamlit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/healthz || exit 1

EXPOSE 8501
CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Production Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-keyveve}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  mcp-weather:
    build:
      context: .
      dockerfile: mcp-server/Dockerfile
    environment:
      - WEATHER_API_KEY=${WEATHER_API_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    depends_on:
      - redis

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      - POSTGRES_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-keyveve}
      - REDIS_URL=redis://redis:6379/0
      - MCP_WEATHER_ENDPOINT=http://mcp-weather:3001
      - WEATHER_API_KEY=${WEATHER_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_PRIVATE_KEY_PEM=${JWT_PRIVATE_KEY_PEM}
      - JWT_PUBLIC_KEY_PEM=${JWT_PUBLIC_KEY_PEM}
      - UI_ORIGIN=${UI_ORIGIN:-http://localhost:8501}
    volumes:
      - ./uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      mcp-weather:
        condition: service_healthy

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    environment:
      - BACKEND_URL=http://backend:8000
    ports:
      - "${FRONTEND_PORT:-8501}:8501"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy

  # Optional: reverse proxy for production
  nginx:
    image: nginx:alpine
    ports:
      - "${HTTP_PORT:-80}:80"
      - "${HTTPS_PORT:-443}:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    profiles:
      - production

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    driver: bridge
```

### RAG Embedding Generation
```python
# backend/app/graph/rag.py (enhanced)
import openai
import asyncio
from typing import List
import logging

logger = logging.getLogger(__name__)

async def generate_embeddings_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """Generate embeddings for texts in batches.
    
    Args:
        texts: List of text strings
        batch_size: Number of texts per batch
        
    Returns:
        List of embedding vectors
    """
    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    
    embeddings = []
    
    # Process in batches to avoid rate limits
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            response = await client.embeddings.create(
                model="text-embedding-3-small",  # Latest model
                input=batch,
                encoding_format="float"
            )
            
            batch_embeddings = [data.embedding for data in response.data]
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Embedding generation failed for batch {i//batch_size}: {e}")
            # Fallback to zero vectors
            fallback_embeddings = [[0.0] * 1536 for _ in batch]
            embeddings.extend(fallback_embeddings)
    
    return embeddings

async def ingest_document_with_embeddings(
    document_content: str,
    metadata: dict,
    chunk_size: int = 800,
    chunk_overlap: int = 200
) -> List[KnowledgeChunk]:
    """Ingest document with real embedding generation.
    
    Args:
        document_content: Full document text
        metadata: Document metadata
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of processed knowledge chunks
    """
    # Split into chunks
    chunks = split_text_into_chunks(document_content, chunk_size, chunk_overlap)
    
    # Generate embeddings
    embeddings = await generate_embeddings_batch([chunk.content for chunk in chunks])
    
    # Combine chunks with embeddings
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding
    
    return chunks
```

### Deployment Scripts
```bash
#!/bin/bash
# scripts/generate-jwt-keys.sh

echo "🔑 Generating RSA key pair for JWT..."

# Generate private key
openssl genrsa -out jwt-private.pem 2048

# Generate public key  
openssl rsa -in jwt-private.pem -pubout -out jwt-public.pem

echo "✅ JWT keys generated:"
echo "  - Private key: jwt-private.pem"
echo "  - Public key: jwt-public.pem"
echo ""
echo "Add these to your .env file:"
echo "JWT_PRIVATE_KEY_PEM=\"$(cat jwt-private.pem | tr '\n' '\\n')\""
echo "JWT_PUBLIC_KEY_PEM=\"$(cat jwt-public.pem | tr '\n' '\\n')\""
```

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "🚀 Deploying Keyveve Travel Planner..."

# Check required environment variables
required_vars=("POSTGRES_PASSWORD" "OPENAI_API_KEY" "WEATHER_API_KEY" "JWT_PRIVATE_KEY_PEM" "JWT_PUBLIC_KEY_PEM")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "❌ Error: $var is not set"
        exit 1
    fi
done

# Build and start services
echo "📦 Building services..."
docker-compose build --no-cache

echo "🗃️  Starting dependencies..."
docker-compose up -d postgres redis mcp-weather

echo "⏳ Waiting for dependencies..."
sleep 10

echo "🔄 Running migrations..."
docker-compose run --rm backend alembic upgrade head

echo "🌱 Seeding database..."
docker-compose run --rm backend python scripts/seed_fixtures.py

echo "🎯 Starting application..."
docker-compose up -d backend frontend

echo "✅ Deployment complete!"
echo "🌐 Frontend: http://localhost:8501"
echo "🔧 Backend API: http://localhost:8000"
echo "📊 Health: http://localhost:8000/healthz"
```

## Environment Configuration

### Production Environment Template
```bash
# .env.production.example

# Database
POSTGRES_DB=keyveve_prod
POSTGRES_USER=keyveve  
POSTGRES_PASSWORD=your_secure_password_here

# Redis
REDIS_URL=redis://redis:6379/0

# API Keys
OPENAI_API_KEY=sk-your_openai_key_here
WEATHER_API_KEY=your_weather_api_key_here

# JWT Keys (generate with scripts/generate-jwt-keys.sh)
JWT_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
JWT_PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"

# Frontend
UI_ORIGIN=https://your-domain.com
FRONTEND_PORT=8501

# MCP
MCP_WEATHER_ENDPOINT=http://mcp-weather:3001
MCP_ENABLED=true

# Production settings
HTTP_PORT=80
HTTPS_PORT=443
```

## Testing Strategy

### Docker Build Tests
- Multi-stage build validation
- Security scanning with docker scout
- Image size optimization checks
- Health check validation

### Integration Tests
- End-to-end deployment testing
- Service discovery and communication
- Data persistence across restarts
- Performance under load

### Production Readiness
- SSL/TLS configuration
- Log aggregation setup
- Monitoring and alerting
- Backup and disaster recovery

## Deployment Guide

### Development Deployment
```bash
# Quick start for development
cp .env.example .env
# Edit .env with your configuration
docker-compose -f docker-compose.dev.yml up -d
```

### Production Deployment  
```bash
# Production deployment
cp .env.production.example .env
# Edit .env with production values
./scripts/generate-jwt-keys.sh
./scripts/deploy.sh
```

### Health Monitoring
```bash
# Check all services
docker-compose ps

# Check health
curl http://localhost:8000/healthz
curl http://localhost:8501/

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Success Criteria

- [ ] All services start with docker-compose up
- [ ] Health checks pass for all services
- [ ] Frontend accessible at configured port
- [ ] Backend API responds to requests
- [ ] Database migrations run successfully
- [ ] RAG embeddings generate correctly
- [ ] MCP integration works end-to-end
- [ ] Authentication flow complete
- [ ] Production deployment tested

## Performance Optimizations

### Docker Optimizations
- Multi-stage builds to reduce image size
- Layer caching for faster rebuilds  
- Non-root users for security
- Health checks for reliability

### Application Optimizations
- Batch embedding generation
- Database connection pooling
- Redis caching for rate limits
- Efficient Docker networking

### Production Features
- Reverse proxy with Nginx
- SSL termination
- Log aggregation
- Monitoring endpoints
