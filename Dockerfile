# Multi-stage Dockerfile optimized for M1 Mac
FROM python:3.11-slim as builder

# Set build arguments
ARG POETRY_VERSION=1.6.1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==$POETRY_VERSION

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/opt/poetry \
    POETRY_HOME="/opt/poetry"

WORKDIR /app

# Copy Poetry metadata required for dependency installation
COPY pyproject.toml poetry.lock* ./
COPY README.md ./

# Install runtime dependencies only (project source copied later)
RUN poetry install --only main --no-root && rm -rf $POETRY_CACHE_DIR

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --system --gid=1001 appgroup && \
    useradd --system --gid=appgroup --uid=1001 --shell=/bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Ensure we use the venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup contracts/ ./contracts/
COPY --chown=appuser:appgroup scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/logs && chown appuser:appgroup /app/logs

# Make scripts executable
RUN chmod +x /app/scripts/*.sh || true

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Set entrypoint and default command
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["python", "-m", "hermes_odoo_adapter.main"]
