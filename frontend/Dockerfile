FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
# Note: In a real setup, you'd have a requirements.txt for frontend
# For now, we'll install streamlit and requests directly
RUN pip install --no-cache-dir \
    streamlit>=1.39.0 \
    requests>=2.31.0 \
    pandas>=2.0.0 \
    plotly>=5.17.0 \
    httpx>=0.27.0

# Create non-root user
RUN adduser --disabled-password --gecos '' streamlit

# Copy frontend code
COPY frontend/ ./

# Create .streamlit directory and config
RUN mkdir -p .streamlit

# Change ownership
RUN chown -R streamlit:streamlit /app
USER streamlit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.fileWatcherType=none"]
