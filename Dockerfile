# HERMES Odoo Adapter v2.0 — Hybrid ROS2 (Vulcanexus) + FastAPI
#
# Build context: repo root (ARISE/) so we can access hermes_msgs.
#   docker build -f hermes_odoo_adapter/Dockerfile .
#
# Protocols: DDS (Fast-DDS via Vulcanexus), JSON-RPC, NGSI-LD, SOAP 1.1

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

# Build hermes_msgs (ROS2 service/message types)
WORKDIR /opt/hermes_ws
COPY hermes_main/ros2_ws/src/hermes_msgs /opt/hermes_ws/src/hermes_msgs
RUN . /opt/ros/humble/setup.sh && \
    colcon build --packages-select hermes_msgs && \
    rm -rf build log

# Install Python dependencies via Poetry (no virtualenv — system Python)
WORKDIR /app
COPY hermes_odoo_adapter/pyproject.toml hermes_odoo_adapter/poetry.lock* ./
COPY hermes_odoo_adapter/README.md ./
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

# Copy application code
COPY hermes_odoo_adapter/src/ ./src/
COPY hermes_odoo_adapter/contracts/ ./contracts/
COPY hermes_odoo_adapter/scripts/ ./scripts/

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
COPY hermes_odoo_adapter/scripts/docker-entrypoint-ros2.sh /docker-entrypoint-ros2.sh
RUN chmod +x /docker-entrypoint-ros2.sh

ENTRYPOINT ["/docker-entrypoint-ros2.sh"]
CMD ["python3", "-m", "hermes_odoo_adapter.main"]
