# ==============================================================================
# Crypto Quant Monitor — Production Multi-Service Container
# ==============================================================================

FROM python:3.11-slim as base

# Set environment variables for non-interactive and unbuffered execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install necessary system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install application dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create application directories for persistent volumes
RUN mkdir -p /app/data /app/logs /app/config

# Create a non-root dedicated application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser && \
    chown -R appuser:appgroup /app

# Copy application source code
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup config/ /app/config/
COPY --chown=appuser:appgroup scripts/ /app/scripts/
COPY --chown=appuser:appgroup .env.example /app/.env.example

# Switch to non-root execution
USER appuser

# Expose API Gateway (8000) and Dashboard UI (8501)
EXPOSE 8000 8501

# Default execution: run the unified entrypoint
ENTRYPOINT ["python", "scripts/entrypoint.py"]
CMD ["api"]
