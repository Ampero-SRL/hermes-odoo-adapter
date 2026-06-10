#!/usr/bin/env bash
# Hit the adapter readiness endpoint — checks each backing subsystem
# (Odoo, Orion-LD, warehouse, ROS 2).
#
# Expected output (ReadinessResponse model in main.py):
#   {
#     "status": "ready",
#     "checks": {
#       "odoo": true,
#       "orion": true,
#       "warehouse": true,
#       "ros2": true
#     },
#     "details": {
#       "odoo": "Connected",
#       "orion": "Connected",
#       "warehouse": "Connected (null)",
#       "ros2": "Node 'hermes_adapter' running"
#     }
#   }
#
# `status: "not_ready"` (and HTTP 200, not 5xx) means at least one
# subsystem reported false; check the per-key `details` for the reason.

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
curl -sf "${ADAPTER_URL}/readyz" | (command -v jq > /dev/null && jq . || cat)
