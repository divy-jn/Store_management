# ──────────────────────────────────────────────
# Store Intelligence API — Dockerfile
# Multi-stage build for production
# ──────────────────────────────────────────────

# Stage 1: Dependencies
FROM python:3.12-slim AS dependencies

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Application
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY app/ ./app/
COPY store_layout.json .
RUN mkdir -p "./Project details/New folder"
COPY ["Project details/New folder/POS - sample transactionsb1e826f.csv", "./Project details/New folder/POS - sample transactionsb1e826f.csv"]
COPY ["Project details/Brigade_Bangalore_10_April_26 (1)bc6219c.csv", "./Project details/Brigade_Bangalore_10_April_26 (1)bc6219c.csv"]

# Copy dashboard
COPY dashboard/ ./dashboard/

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose API port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
