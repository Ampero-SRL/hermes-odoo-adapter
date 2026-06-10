#!/usr/bin/env bash
# Subscribe to the ROS4HRI Intent stream the adapter publishes
# (Sprint 0.4). The adapter logs every Intent on the adapter container's
# stdout AND emits the actual `hri_actions_msgs/Intent` message on
# `/intents`; this script lets you watch the wire-level message in real
# time.
#
# Run from a Vulcanexus / ROS 2 Humble shell. The simplest invocation is
# inside the running adapter container:
#
#   docker compose -f docker/docker-compose.demo.yml exec adapter \
#       bash -lc '
#           source /opt/ros/humble/setup.bash &&
#           source /opt/hermes_ws/install/setup.bash &&
#           bash /app/examples/ros2/06_intents_echo.sh
#       '
#
# Trigger an Intent from another shell while this runs, e.g.:
#
#   curl -sS -X POST http://localhost:8080/admin/recompute/demo-ctrl-1 \
#       -H "Content-Type: application/json" \
#       -d '{"projectCode":"DEMO-CTRL"}'
#
# Expected output (the first Intent fires within ~1 s of the recompute):
#   ---
#   intent: START_ACTIVITY
#   source: erp/odoo
#   modality: MODALITY_OTHER
#   priority: 128
#   confidence: 1.0
#   data: '{"activity":"manufacturing_order","goal":"fulfill_kit",
#          "object":{"type":"manufacturing_order","id":"1"},
#          "project_id":"demo-ctrl-1","bom":[...]}'
#   ---
#
# `--no-daemon` avoids the rclpy daemon races that sometimes hit
# short-lived ros2 CLI invocations inside compose containers.

set -euo pipefail

# Best-effort: list before subscribing so the daemon publishes are
# already announced.
ros2 topic list --no-daemon 2>/dev/null | grep -E "^/intents$" \
    || echo "(note: /intents not yet visible in topic list; the publisher exists — it just takes a moment for the daemon to discover it.)"

ros2 topic echo --no-daemon /intents hri_actions_msgs/msg/Intent
