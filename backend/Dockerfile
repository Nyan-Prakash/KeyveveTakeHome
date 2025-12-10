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

# Copy application code first
COPY backend/ backend/
COPY scripts/ scripts/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY eval/ eval/

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies directly from pyproject.toml (not editable mode)
RUN pip install --no-cache-dir \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    sqlalchemy>=2.0.0 \
    alembic>=1.12.0 \
    psycopg2-binary>=2.9.0 \
    pgvector>=0.2.0 \
    redis>=5.0.0 \
    langgraph>=0.2.0 \
    langchain-core>=0.3.0 \
    fastapi>=0.115.0 \
    uvicorn>=0.32.0 \
    httpx>=0.27.0 \
    streamlit>=1.39.0 \
    sse-starlette>=2.1.0 \
    openai>=1.0.0 \
    tiktoken>=0.5.0 \
    argon2-cffi>=23.1.0 \
    pyjwt[crypto]>=2.8.0 \
    cryptography>=41.0.0 \
    python-multipart>=0.0.6 \
    email-validator>=2.0.0 \
    pymupdf>=1.23.0 \
    pytesseract>=0.3.10 \
    pillow>=10.0.0 \
    pdf2image>=1.16.0 \
    pyyaml>=6.0.1 \
    python-dateutil>=2.8.0

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

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
