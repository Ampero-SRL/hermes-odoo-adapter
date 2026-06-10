# HERMES Odoo Adapter v2.0 — Hybrid ROS2 (Vulcanexus) + FastAPI
#
# Self-contained build from the adapter repo alone:
#   docker build -t hermes-odoo-adapter .
#   # or via compose:
#   docker compose -f docker/docker-compose.demo.yml up
#
# Build context: adapter repo root (the directory containing this file).
# All required ROS 2 message definitions (`hermes_msgs`) are vendored under
# `ros2_ws/src/hermes_msgs/` — see `ros2_ws/src/hermes_msgs/VENDORED_FROM.md`.
#
# Protocols: DDS (Fast-DDS via Vulcanexus), JSON-RPC (Odoo), NGSI-LD
# (Orion-LD), SOAP 1.1 (Hanel).

# ── Stage 1: Build hermes_msgs + install Python deps ─────────────────
FROM eprosima/vulcanexus:humble AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Build tools + Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-pip \
        build-essential \
        curl \
    && pip install --no-cache-dir poetry==1.6.1 \
    && rm -rf /var/lib/apt/lists/*

# Build the vendored hermes_msgs package (ROS2 service / message types
# the adapter consumes — see ros2_ws/src/hermes_msgs/VENDORED_FROM.md).
WORKDIR /opt/hermes_ws
COPY ros2_ws/src/hermes_msgs /opt/hermes_ws/src/hermes_msgs
RUN . /opt/ros/humble/setup.sh && \
    colcon build --packages-select hermes_msgs && \
    rm -rf build log

# Install Python dependencies via Poetry (no virtualenv — system Python)
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
COPY README.md ./
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-root && \
    rm -rf /root/.cache

# ── Stage 2: Production image ────────────────────────────────────────
FROM eprosima/vulcanexus:humble AS production

ENV DEBIAN_FRONTEND=noninteractive

# Minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy built hermes_msgs workspace
COPY --from=builder /opt/hermes_ws/install /opt/hermes_ws/install

# Copy installed Python packages (system site-packages)
COPY --from=builder /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages

WORKDIR /app

ENV PYTHONPATH=/app/src

# Copy application code (paths relative to the adapter repo root).
COPY src/ ./src/
COPY contracts/ ./contracts/
COPY scripts/ ./scripts/

# Create log directory
RUN mkdir -p /app/logs

# Make scripts executable
RUN chmod +x /app/scripts/*.sh || true

# Expose ports (FastAPI + Prometheus metrics)
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Entrypoint sources ROS2 setup, then runs the adapter
COPY scripts/docker-entrypoint-ros2.sh /docker-entrypoint-ros2.sh
RUN chmod +x /docker-entrypoint-ros2.sh

ENTRYPOINT ["/docker-entrypoint-ros2.sh"]
CMD ["python3", "-m", "hermes_odoo_adapter.main"]
