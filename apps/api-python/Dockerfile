# =============================================================================
# EcoTrack Python API — Multi-stage Dockerfile
# =============================================================================

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy package definitions
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/core/ecotrack/ packages/core/ecotrack/
COPY packages/geo/pyproject.toml packages/geo/pyproject.toml
COPY packages/geo/ecotrack_geo/ packages/geo/ecotrack_geo/
COPY packages/ml/pyproject.toml packages/ml/pyproject.toml
COPY packages/ml/ecotrack_ml/ packages/ml/ecotrack_ml/
COPY apps/api-python/pyproject.toml apps/api-python/pyproject.toml
COPY apps/api-python/ecotrack_api/ apps/api-python/ecotrack_api/

# Install packages
RUN pip install --no-cache-dir \
    -e packages/core \
    -e packages/geo \
    -e packages/ml \
    -e apps/api-python

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY packages/core/ /app/packages/core/
COPY packages/geo/ /app/packages/geo/
COPY packages/ml/ /app/packages/ml/
COPY apps/api-python/ /app/apps/api-python/

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ECOTRACK_ENV=production \
    ECOTRACK_DEBUG=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "ecotrack_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
