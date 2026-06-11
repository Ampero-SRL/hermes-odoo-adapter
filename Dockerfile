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
FROM eprosima/vulcanexus:humble@sha256:595c7f1360008fb92e79a1232837dcabc30e434636df8c59500090619b75a839 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Build tools + Poetry + vcstool (for fetching hri_actions_msgs).
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-vcstool \
        python3-pip \
        build-essential \
        curl \
        git \
    && pip install --no-cache-dir poetry==1.6.1 \
    && rm -rf /var/lib/apt/lists/*

# Build the vendored hermes_msgs + the hermes_odoo_adapter_launch
# ament wrapper. Fetch hri_actions_msgs from source (deps.repos
# pinned to humble-devel) in the same workspace so the ROS4HRI Intent
# publisher can import hri_actions_msgs.msg.Intent at runtime and the
# launch wrapper can be `ros2 launch hermes_odoo_adapter_launch ...`d.
WORKDIR /opt/hermes_ws
COPY ros2_ws/src/hermes_msgs /opt/hermes_ws/src/hermes_msgs
COPY ros2_ws/src/hermes_odoo_adapter_launch /opt/hermes_ws/src/hermes_odoo_adapter_launch
COPY ros2_ws/deps.repos /opt/hermes_ws/deps.repos
RUN vcs import src < deps.repos && \
    . /opt/ros/humble/setup.sh && \
    colcon build --packages-select \
        hermes_msgs hri_actions_msgs hermes_odoo_adapter_launch && \
    rm -rf build log

# Install Python dependencies via Poetry (no virtualenv — system Python)
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
COPY README.md ./
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-root && \
    rm -rf /root/.cache

# ── Stage 2: Production image ────────────────────────────────────────
# Pinned by digest for the D4 submission's 2033-stability commitment
# (D4 §3.2.1) — the floating `humble` tag is avoided so a rebuild years
# from now produces byte-identical layers. To bump:
#   docker pull eprosima/vulcanexus:humble
#   docker image inspect eprosima/vulcanexus:humble \
#       --format '{{index .RepoDigests 0}}'
# …and replace the sha256 below in BOTH FROM lines.
FROM eprosima/vulcanexus:humble@sha256:595c7f1360008fb92e79a1232837dcabc30e434636df8c59500090619b75a839 AS production

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
# Ship `examples/` inside the image so reviewers can invoke the
# hello-world / basic-demo scripts via
#   docker compose exec adapter bash /app/examples/<...>.sh
# without mounting the host repo.
COPY examples/ ./examples/
# project_mapping.json is referenced by .env.example (and required by
# workers/project_sync.py to resolve a Project code to the Odoo product
# behind it). Ship it inside the image so the demo flow works on a
# fresh clone without extra mounts.
COPY project_mapping.json ./project_mapping.json
# Ship `launch/` so the `ros2 launch /app/launch/...` path documented in
# launch/README.md actually works inside the container.
COPY launch/ ./launch/

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
