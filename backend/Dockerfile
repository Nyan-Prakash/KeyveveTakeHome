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
        curl \
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
COPY eval/ eval/

# Create uploads directory
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

# Change ownership
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

# Use factory pattern for app creation
# Run database migrations before starting the server
CMD sh -c "alembic upgrade head && uvicorn backend.app.main:create_app --host 0.0.0.0 --port 8000 --factory"
